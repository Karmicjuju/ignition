from __future__ import annotations

import asyncio
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ignition.core.logging import get_logger
from ignition.schemas.catalog import InstallMethod, ToolInfo
from ignition.schemas.state import AppStateModel, InstallEvent

_LOCAL_BIN = Path.home() / ".local" / "bin"


@dataclass
class InstallResult:
    """Result of a single tool install attempt."""

    tool_key: str
    success: bool
    method_used: InstallMethod
    error: str | None = None
    detected_version: str | None = None


async def _run_subprocess(args: list[str]) -> tuple[int, str, str]:
    """Run a subprocess and return (returncode, stdout, stderr)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        return (
            proc.returncode or 0,
            stdout_bytes.decode("utf-8", errors="replace").strip(),
            stderr_bytes.decode("utf-8", errors="replace").strip(),
        )
    except FileNotFoundError:
        return (127, "", f"executable not found: {args[0]}")
    except Exception as exc:
        return (1, "", str(exc))


class InstallerEngine:
    """Platform-aware tool installer.

    Dispatches to the correct install method (brew, apt, binary, copy-paste)
    based on the current platform and tool manifest. Records install history
    in AppStateModel.

    Instance caches:
      _brew_available: bool | None — result of `which brew` check
      _apt_updated: bool — whether `apt-get update` has been run this session
    """

    _POLL_INTERVAL_SECONDS = 5
    _POLL_MAX_SECONDS = 120

    def __init__(self, state: AppStateModel) -> None:
        self._log = get_logger("ignition.core.installer")
        self._state = state
        self._brew_available: bool | None = None
        self._apt_updated: bool = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def install(
        self,
        tool: ToolInfo,
        progress_cb: Callable[[str], None] | None = None,
    ) -> InstallResult:
        """Install a single tool and record the event in state.

        Args:
            tool: The ToolInfo to install.
            progress_cb: Optional callback invoked with status message strings.

        Returns:
            An InstallResult describing the outcome.
        """
        method = self.resolve_method(tool)
        self._log.info("installer.install.start", tool_key=tool.key, method=method)

        if progress_cb:
            progress_cb(f"Installing {tool.name} via {method}…")

        result = await self._dispatch(tool, method, progress_cb)

        # Record in install history (cap enforced by Pydantic validator)
        event = InstallEvent(
            timestamp=datetime.now(UTC),
            tool_key=tool.key,
            method=method,
            success=result.success,
            version=result.detected_version,
        )
        self._state.install_history.append(event)
        if len(self._state.install_history) > 100:
            self._state.install_history = self._state.install_history[-100:]

        self._log.info(
            "installer.install.complete",
            tool_key=tool.key,
            success=result.success,
            method=method,
        )
        return result

    async def install_bundle(
        self,
        tools: list[ToolInfo],
        progress_cb: Callable[[str, str], None] | None = None,
    ) -> list[InstallResult]:
        """Install a list of tools sequentially to avoid package manager lock contention.

        Args:
            tools: Tools to install in order.
            progress_cb: Optional callback with (tool_key, status_message).

        Returns:
            List of InstallResult in the same order as tools.
        """
        results: list[InstallResult] = []
        for tool in tools:
            tool_cb: Callable[[str], None] | None = None
            if progress_cb:

                def _make_cb(key: str) -> Callable[[str], None]:
                    def _cb(msg: str) -> None:
                        progress_cb(key, msg)

                    return _cb

                tool_cb = _make_cb(tool.key)

            result = await self.install(tool, progress_cb=tool_cb)
            results.append(result)

        installed = sum(1 for r in results if r.success)
        failed = sum(1 for r in results if not r.success)
        self._log.info("installer.bundle.complete", installed=installed, failed=failed)
        return results

    def resolve_method(self, tool: ToolInfo) -> InstallMethod:
        """Return the best install method for tool on the current platform.

        Decision tree:
          macOS:
            - Homebrew available AND brew step present → BREW
            - Binary step present → BINARY
            - Falls back to COPY_PASTE if no other method
          Linux:
            - apt step present → APT (with sudo-required copy-paste for privileged op)
            - Binary step present → BINARY
            - Falls back to COPY_PASTE if no other method
        """
        is_macos = sys.platform == "darwin"
        platform_steps = tool.install_methods.macos if is_macos else tool.install_methods.linux

        has_brew = any(s.method == InstallMethod.BREW for s in platform_steps)
        has_apt = any(s.method == InstallMethod.APT for s in platform_steps)
        has_binary = any(s.method == InstallMethod.BINARY for s in platform_steps)

        if is_macos:
            if has_brew and self._is_brew_available():
                return InstallMethod.BREW
            if has_binary:
                return InstallMethod.BINARY
            # No suitable direct method — must surface copy-paste
            return InstallMethod.COPY_PASTE

        # Linux
        if has_apt:
            if tool.requires_sudo:
                return InstallMethod.COPY_PASTE
            return InstallMethod.APT
        if has_binary:
            return InstallMethod.BINARY
        return InstallMethod.COPY_PASTE

    # ------------------------------------------------------------------
    # Caching helpers
    # ------------------------------------------------------------------

    def _is_brew_available(self) -> bool:
        """Return whether `brew` is on PATH, caching the result per instance."""
        if self._brew_available is None:
            import shutil

            self._brew_available = shutil.which("brew") is not None
            self._log.info("installer.brew_check", available=self._brew_available)
        return self._brew_available

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def _dispatch(
        self,
        tool: ToolInfo,
        method: InstallMethod,
        progress_cb: Callable[[str], None] | None,
    ) -> InstallResult:
        """Route to the right install handler."""
        if method == InstallMethod.BREW:
            return await self._install_brew(tool, progress_cb)
        if method == InstallMethod.APT:
            return await self._install_apt(tool, progress_cb)
        if method == InstallMethod.BINARY:
            return await self._install_binary(tool, progress_cb)
        # COPY_PASTE — surface the command, poll for binary
        return await self._install_copy_paste(tool, progress_cb)

    # ------------------------------------------------------------------
    # Brew install
    # ------------------------------------------------------------------

    async def _install_brew(
        self,
        tool: ToolInfo,
        progress_cb: Callable[[str], None] | None,
    ) -> InstallResult:
        step = next(
            (s for s in tool.install_methods.macos if s.method == InstallMethod.BREW),
            None,
        )
        if step is None:
            return InstallResult(
                tool_key=tool.key,
                success=False,
                method_used=InstallMethod.BREW,
                error="No brew step found in manifest",
            )

        formula = step.package or tool.key
        args = ["brew", "install"]
        if step.cask:
            args = ["brew", "install", "--cask"]
        args.append(formula)

        if progress_cb:
            progress_cb(f"brew install {formula}…")

        rc, stdout, stderr = await _run_subprocess(args)
        if rc != 0:
            self._log.warning("installer.brew.failed", tool_key=tool.key, stderr=stderr)
            return InstallResult(
                tool_key=tool.key,
                success=False,
                method_used=InstallMethod.BREW,
                error=stderr or stdout,
            )

        version = await self._detect_version(tool)
        return InstallResult(
            tool_key=tool.key,
            success=True,
            method_used=InstallMethod.BREW,
            detected_version=version,
        )

    # ------------------------------------------------------------------
    # Apt install (direct, no sudo; sudo path goes through COPY_PASTE)
    # ------------------------------------------------------------------

    async def _install_apt(
        self,
        tool: ToolInfo,
        progress_cb: Callable[[str], None] | None,
    ) -> InstallResult:
        step = next(
            (s for s in tool.install_methods.linux if s.method == InstallMethod.APT),
            None,
        )
        if step is None:
            return InstallResult(
                tool_key=tool.key,
                success=False,
                method_used=InstallMethod.APT,
                error="No apt step found in manifest",
            )

        package = step.package or tool.key

        if not self._apt_updated:
            if progress_cb:
                progress_cb("Running apt-get update…")
            rc_up, _, stderr_up = await _run_subprocess(["apt-get", "update", "-q"])
            if rc_up == 0:
                self._apt_updated = True
            else:
                self._log.warning("installer.apt_update.failed", stderr=stderr_up)

        if progress_cb:
            progress_cb(f"apt-get install -y {package}…")

        rc, stdout, stderr = await _run_subprocess(["apt-get", "install", "-y", package])
        if rc != 0:
            self._log.warning("installer.apt.failed", tool_key=tool.key, stderr=stderr)
            return InstallResult(
                tool_key=tool.key,
                success=False,
                method_used=InstallMethod.APT,
                error=stderr or stdout,
            )

        version = await self._detect_version(tool)
        return InstallResult(
            tool_key=tool.key,
            success=True,
            method_used=InstallMethod.APT,
            detected_version=version,
        )

    # ------------------------------------------------------------------
    # Binary install (direct download to ~/.local/bin)
    # ------------------------------------------------------------------

    async def _install_binary(
        self,
        tool: ToolInfo,
        progress_cb: Callable[[str], None] | None,
    ) -> InstallResult:
        is_macos = sys.platform == "darwin"
        platform_steps = tool.install_methods.macos if is_macos else tool.install_methods.linux
        step = next(
            (s for s in platform_steps if s.method == InstallMethod.BINARY),
            None,
        )
        if step is None or not step.url:
            self._log.warning("installer.binary.no_url", tool_key=tool.key)
            return InstallResult(
                tool_key=tool.key,
                success=False,
                method_used=InstallMethod.BINARY,
                error="No binary_url in manifest for this platform",
            )

        url = step.url
        binary_name = step.binary_name or tool.key

        if progress_cb:
            progress_cb(f"Downloading {binary_name} from {url}…")

        # Ensure target directory exists
        _LOCAL_BIN.mkdir(parents=True, exist_ok=True)
        dest = _LOCAL_BIN / Path(binary_name).name

        # Download using curl
        rc, stdout, stderr = await _run_subprocess(["curl", "-fsSL", "-o", str(dest), url])
        if rc != 0:
            self._log.warning("installer.binary.download_failed", tool_key=tool.key, stderr=stderr)
            return InstallResult(
                tool_key=tool.key,
                success=False,
                method_used=InstallMethod.BINARY,
                error=f"Download failed: {stderr or stdout}",
            )

        # Make executable
        try:
            dest.chmod(0o755)
        except Exception as exc:
            return InstallResult(
                tool_key=tool.key,
                success=False,
                method_used=InstallMethod.BINARY,
                error=f"chmod failed: {exc}",
            )

        # Warn if ~/.local/bin is not on PATH
        self._maybe_warn_path(progress_cb)

        version = await self._detect_version(tool)
        return InstallResult(
            tool_key=tool.key,
            success=True,
            method_used=InstallMethod.BINARY,
            detected_version=version,
        )

    def _maybe_warn_path(self, progress_cb: Callable[[str], None] | None) -> None:
        """If ~/.local/bin is not on PATH, emit a warning via progress_cb."""
        local_bin_str = str(_LOCAL_BIN)
        path_env = os.environ.get("PATH", "")
        path_dirs = path_env.split(os.pathsep)
        if local_bin_str not in path_dirs:
            msg = (
                "Warning: ~/.local/bin is not on PATH. "
                "Restart your terminal or run `source ~/.zshrc` to add it."
            )
            self._log.warning("installer.binary.path_not_set", local_bin=local_bin_str)
            if progress_cb:
                progress_cb(msg)

    # ------------------------------------------------------------------
    # Copy-paste (sudo / privileged operations)
    # ------------------------------------------------------------------

    async def _install_copy_paste(
        self,
        tool: ToolInfo,
        progress_cb: Callable[[str], None] | None,
    ) -> InstallResult:
        """Surface a copy-paste command block and poll for binary presence.

        Polls every 5 s for up to 2 minutes. Marks INSTALLED when binary detected.
        """
        is_macos = sys.platform == "darwin"
        platform_steps = tool.install_methods.macos if is_macos else tool.install_methods.linux

        # Build the suggested command from the first available step
        cmd: str
        apt_step = next((s for s in platform_steps if s.method == InstallMethod.APT), None)
        if apt_step:
            package = apt_step.package or tool.key
            cmd = f"sudo apt-get install -y {package}"
        else:
            cmd = f"# No automated install available for {tool.key} — install manually"

        if progress_cb:
            progress_cb(f"Run this command to install:\n  {cmd}")

        # Poll for binary on PATH
        elapsed = 0
        while elapsed < self._POLL_MAX_SECONDS:
            await asyncio.sleep(self._POLL_INTERVAL_SECONDS)
            elapsed += self._POLL_INTERVAL_SECONDS
            rc, stdout, _ = await _run_subprocess(["which", tool.key])
            if rc == 0 and stdout:
                version = await self._detect_version(tool)
                self._log.info(
                    "installer.copy_paste.detected",
                    tool_key=tool.key,
                    elapsed=elapsed,
                )
                return InstallResult(
                    tool_key=tool.key,
                    success=True,
                    method_used=InstallMethod.COPY_PASTE,
                    detected_version=version,
                )

        self._log.warning(
            "installer.copy_paste.timeout",
            tool_key=tool.key,
            waited_seconds=elapsed,
        )
        return InstallResult(
            tool_key=tool.key,
            success=False,
            method_used=InstallMethod.COPY_PASTE,
            error=f"Timed out waiting for {tool.key} to appear on PATH after {elapsed}s",
        )

    # ------------------------------------------------------------------
    # Version detection
    # ------------------------------------------------------------------

    async def _detect_version(self, tool: ToolInfo) -> str | None:
        """Run the tool's health_check command and return the first stdout line."""
        if not tool.health_check:
            return None
        args = tool.health_check.split()
        rc, stdout, _ = await _run_subprocess(args)
        if rc != 0 or not stdout:
            return None
        return stdout.splitlines()[0]
