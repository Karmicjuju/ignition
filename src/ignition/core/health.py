from __future__ import annotations

import asyncio
import os
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ignition.core.catalog import CatalogService
from ignition.core.logging import get_logger
from ignition.core.state import load_state, save_state
from ignition.schemas.health import CheckResult, FixType, HealthState

# Shell config files to check for Ignition marker, in priority order
_SHELL_CONFIGS = [
    "~/.zshrc",
    "~/.bashrc",
    "~/.profile",
    "~/.bash_profile",
]

_IGNITION_MARKER = "# ignition"

ALL_CATEGORIES = ("tools", "configs", "shell_integration", "permissions")


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


class HealthEngine:
    """Core health scan engine with four check categories."""

    def __init__(self) -> None:
        self._log = get_logger("ignition.core.health")
        self._catalog = CatalogService()
        # Maps check_id → CheckResult for apply_fix to reference
        self._last_results: dict[str, CheckResult] = {}
        # Maps check_id → target path (for AUTO chmod fixes)
        self._fix_targets: dict[str, tuple[Path, int]] = {}

    async def run_scan(self, categories: list[str] | None = None) -> list[CheckResult]:
        """Run all health checks for the given categories (or all if None).

        Returns a flat list of CheckResult. Individual check exceptions are caught
        and reported as NEEDS_ATTENTION rather than crashing the scan.
        """
        targets = list(categories) if categories is not None else list(ALL_CATEGORIES)
        self._log.info("health.scan.start", categories=targets)

        all_results: list[CheckResult] = []

        for category in targets:
            if category == "tools":
                results = await self._scan_tools()
            elif category == "configs":
                results = await self._scan_configs()
            elif category == "shell_integration":
                results = await self._scan_shell_integration()
            elif category == "permissions":
                results = await self._scan_permissions()
            else:
                self._log.warning("health.scan.unknown_category", category=category)
                continue
            all_results.extend(results)

        # Cache results for apply_fix
        self._last_results = {r.check_id: r for r in all_results}

        # Persist scan timestamp and summary to state
        try:
            state = load_state()
            state.last_health_scan = datetime.now(UTC)
            # Summarise worst state per category
            summary: dict[str, str] = {}
            for result in all_results:
                cat = result.category
                existing = summary.get(cat)
                if existing is None:
                    summary[cat] = result.state.value
                else:
                    # Escalate: healthy < recommended < needs_attention < manual
                    _order = {
                        HealthState.HEALTHY: 0,
                        HealthState.RECOMMENDED: 1,
                        HealthState.NEEDS_ATTENTION: 2,
                        HealthState.MANUAL: 3,
                    }
                    current_rank = _order.get(HealthState(existing), 0)
                    new_rank = _order.get(result.state, 0)
                    if new_rank > current_rank:
                        summary[cat] = result.state.value
            state.health_summary = summary
            save_state(state)
        except Exception as exc:
            self._log.warning("health.scan.state_save_failed", reason=str(exc))

        self._log.info("health.scan.complete", total=len(all_results))
        return all_results

    async def apply_fix(self, check_id: str) -> bool:
        """Apply an automatic fix for the given check_id.

        Returns True on success, False if the fix type is not AUTO or the fix fails.
        Only FixType.AUTO fixes are executed; COPY_PASTE fixes require the user to act.
        """
        result = self._last_results.get(check_id)
        if result is None:
            self._log.warning("health.apply_fix.not_found", check_id=check_id)
            return False

        if result.fix_type != FixType.AUTO:
            self._log.info(
                "health.apply_fix.not_auto",
                check_id=check_id,
                fix_type=result.fix_type,
            )
            return False

        fix_info = self._fix_targets.get(check_id)
        if fix_info is None:
            self._log.warning("health.apply_fix.no_target", check_id=check_id)
            return False

        target_path, target_mode = fix_info
        try:
            os.chmod(target_path, target_mode)
            self._log.info(
                "health.apply_fix.success",
                check_id=check_id,
                path=str(target_path),
                mode=oct(target_mode),
            )
            return True
        except Exception as exc:
            self._log.warning(
                "health.apply_fix.failed",
                check_id=check_id,
                reason=str(exc),
            )
            return False

    # ------------------------------------------------------------------ #
    # Category: tools                                                      #
    # ------------------------------------------------------------------ #

    async def _scan_tools(self) -> list[CheckResult]:
        tools = self._catalog.get_all_tools()
        tasks = [self._check_tool(tool) for tool in tools]
        raw: list[Any] = list(await asyncio.gather(*tasks, return_exceptions=True))
        return self._unwrap_results(raw, "tools", "tool_unknown")

    async def _check_tool(self, tool: Any) -> CheckResult:  # tool: ToolInfo
        """Check binary presence and health_check command for a single tool."""
        from ignition.schemas.catalog import ToolInfo

        t: ToolInfo = tool
        check_id = f"tool_{t.key}"

        # Step 1: check binary presence with `which`
        rc_which, stdout_which, _ = await _run_subprocess(["which", t.key])
        binary_present = rc_which == 0 and bool(stdout_which)

        if not binary_present:
            state = HealthState.NEEDS_ATTENTION if t.managed else HealthState.RECOMMENDED
            detail = f"{t.key} binary not found on PATH"
            return CheckResult(
                category="tools",
                check_id=check_id,
                label=t.name,
                state=state,
                detail=detail,
                fix_type=FixType.NONE,
            )

        # Step 2: run health_check if available
        if t.health_check:
            args = t.health_check.split()
            rc_hc, stdout_hc, _ = await _run_subprocess(args)
            if rc_hc != 0:
                return CheckResult(
                    category="tools",
                    check_id=check_id,
                    label=t.name,
                    state=HealthState.RECOMMENDED,
                    detail=f"{t.key} health check failed (exit {rc_hc})",
                    fix_type=FixType.NONE,
                )
            version_hint = stdout_hc.splitlines()[0] if stdout_hc else ""
            detail = f"{t.key} OK — {version_hint}" if version_hint else f"{t.key} OK"
        else:
            detail = f"{t.key} found on PATH"

        return CheckResult(
            category="tools",
            check_id=check_id,
            label=t.name,
            state=HealthState.HEALTHY,
            detail=detail,
            fix_type=FixType.NONE,
        )

    # ------------------------------------------------------------------ #
    # Category: configs                                                    #
    # ------------------------------------------------------------------ #

    async def _scan_configs(self) -> list[CheckResult]:
        tasks = [
            self._check_ignition_marker(),
            self._check_aws_config(),
        ]
        raw: list[Any] = list(await asyncio.gather(*tasks, return_exceptions=True))
        return self._unwrap_results(raw, "configs", "config_unknown")

    async def _check_ignition_marker(self) -> CheckResult:
        """Check if any shell config contains the # ignition marker."""
        home = Path.home()
        found_in: list[str] = []
        for config_str in _SHELL_CONFIGS:
            config_path = home / config_str.lstrip("~/")
            if config_path.exists():
                try:
                    content = config_path.read_text(encoding="utf-8", errors="replace")
                    if _IGNITION_MARKER in content:
                        found_in.append(config_path.name)
                except Exception:
                    pass

        if found_in:
            return CheckResult(
                category="configs",
                check_id="config_ignition_marker",
                label="Ignition shell marker",
                state=HealthState.HEALTHY,
                detail=f"Ignition marker found in: {', '.join(found_in)}",
                fix_type=FixType.NONE,
            )

        # Determine which shell config to suggest appending to
        shell = os.environ.get("SHELL", "")
        if "zsh" in shell:
            suggest = "~/.zshrc"
        elif "bash" in shell:
            suggest = "~/.bashrc"
        else:
            suggest = "~/.profile"

        return CheckResult(
            category="configs",
            check_id="config_ignition_marker",
            label="Ignition shell marker",
            state=HealthState.RECOMMENDED,
            detail=f"Ignition marker not found in any shell config; suggest adding to {suggest}",
            fix_type=FixType.COPY_PASTE,
            fix_command=f"echo '\\n{_IGNITION_MARKER}' >> {suggest}",
        )

    async def _check_aws_config(self) -> CheckResult:
        """Check ~/.aws/config exists when awscli is in the catalog."""
        tools = self._catalog.get_all_tools()
        has_awscli = any(t.key == "awscli" for t in tools)
        aws_config = Path.home() / ".aws" / "config"

        if not has_awscli:
            return CheckResult(
                category="configs",
                check_id="config_aws_config",
                label="AWS config file",
                state=HealthState.HEALTHY,
                detail="awscli not in catalog — no AWS config check required",
                fix_type=FixType.NONE,
            )

        if aws_config.exists():
            return CheckResult(
                category="configs",
                check_id="config_aws_config",
                label="AWS config file",
                state=HealthState.HEALTHY,
                detail="~/.aws/config exists",
                fix_type=FixType.NONE,
            )

        return CheckResult(
            category="configs",
            check_id="config_aws_config",
            label="AWS config file",
            state=HealthState.RECOMMENDED,
            detail="~/.aws/config not found; AWS CLI may not be configured",
            fix_type=FixType.NONE,
        )

    # ------------------------------------------------------------------ #
    # Category: shell_integration                                          #
    # ------------------------------------------------------------------ #

    async def _scan_shell_integration(self) -> list[CheckResult]:
        tasks = [
            self._check_local_bin_path(),
            self._check_local_bin_exists(),
        ]
        raw: list[Any] = list(await asyncio.gather(*tasks, return_exceptions=True))
        return self._unwrap_results(raw, "shell_integration", "shell_unknown")

    async def _check_local_bin_path(self) -> CheckResult:
        """Check if ~/.local/bin is on $PATH."""
        local_bin = str(Path.home() / ".local" / "bin")
        path_env = os.environ.get("PATH", "")
        path_dirs = path_env.split(os.pathsep)

        if local_bin in path_dirs:
            return CheckResult(
                category="shell_integration",
                check_id="shell_local_bin_path",
                label="~/.local/bin on PATH",
                state=HealthState.HEALTHY,
                detail="~/.local/bin is present in $PATH",
                fix_type=FixType.NONE,
            )

        return CheckResult(
            category="shell_integration",
            check_id="shell_local_bin_path",
            label="~/.local/bin on PATH",
            state=HealthState.RECOMMENDED,
            detail="~/.local/bin is not on $PATH — tools installed here won't be found",
            fix_type=FixType.COPY_PASTE,
            fix_command='export PATH="$HOME/.local/bin:$PATH"',
        )

    async def _check_local_bin_exists(self) -> CheckResult:
        """Check if ~/.local/bin exists as a directory."""
        local_bin = Path.home() / ".local" / "bin"

        if local_bin.exists() and local_bin.is_dir():
            return CheckResult(
                category="shell_integration",
                check_id="shell_local_bin_exists",
                label="~/.local/bin directory",
                state=HealthState.HEALTHY,
                detail="~/.local/bin directory exists",
                fix_type=FixType.NONE,
            )

        return CheckResult(
            category="shell_integration",
            check_id="shell_local_bin_exists",
            label="~/.local/bin directory",
            state=HealthState.RECOMMENDED,
            detail="~/.local/bin directory does not exist",
            fix_type=FixType.COPY_PASTE,
            fix_command="mkdir -p ~/.local/bin",
        )

    # ------------------------------------------------------------------ #
    # Category: permissions                                                #
    # ------------------------------------------------------------------ #

    async def _scan_permissions(self) -> list[CheckResult]:
        tasks = [
            *self._ssh_key_check_tasks(),
            self._check_aws_credentials_perms(),
            self._check_local_bin_writable(),
        ]
        raw: list[Any] = list(await asyncio.gather(*tasks, return_exceptions=True))
        return self._unwrap_results(raw, "permissions", "perm_unknown")

    def _ssh_key_check_tasks(self) -> list[Any]:
        """Return a list of coroutines — one per SSH key file found."""
        ssh_dir = Path.home() / ".ssh"
        tasks = []
        if ssh_dir.exists() and ssh_dir.is_dir():
            for key_file in ssh_dir.iterdir():
                if key_file.is_file() and not key_file.name.startswith("."):
                    tasks.append(self._check_ssh_key(key_file))
        if not tasks:
            # Return a synthetic healthy result when no keys are present
            tasks.append(self._no_ssh_keys_result())
        return tasks

    async def _no_ssh_keys_result(self) -> CheckResult:
        return CheckResult(
            category="permissions",
            check_id="perm_ssh_no_keys",
            label="SSH keys",
            state=HealthState.HEALTHY,
            detail="No SSH key files found in ~/.ssh/",
            fix_type=FixType.NONE,
        )

    async def _check_ssh_key(self, key_file: Path) -> CheckResult:
        """Check SSH key file permissions."""
        is_public = key_file.suffix == ".pub"
        expected_mode = 0o644 if is_public else 0o600
        check_id = f"perm_ssh_{key_file.name.replace('.', '_')}"

        try:
            file_stat = key_file.stat()
            actual_mode = stat.S_IMODE(file_stat.st_mode)
        except Exception as exc:
            return CheckResult(
                category="permissions",
                check_id=check_id,
                label=f"SSH key: {key_file.name}",
                state=HealthState.NEEDS_ATTENTION,
                detail=f"Could not stat {key_file.name}: {exc}",
                fix_type=FixType.NONE,
            )

        if actual_mode == expected_mode:
            return CheckResult(
                category="permissions",
                check_id=check_id,
                label=f"SSH key: {key_file.name}",
                state=HealthState.HEALTHY,
                detail=f"{key_file.name} has correct mode {oct(expected_mode)}",
                fix_type=FixType.NONE,
            )

        # Determine if user owns the file
        try:
            owner_uid = file_stat.st_uid
            user_owns = owner_uid == os.getuid()
        except Exception:
            user_owns = False

        if user_owns:
            self._fix_targets[check_id] = (key_file, expected_mode)
            return CheckResult(
                category="permissions",
                check_id=check_id,
                label=f"SSH key: {key_file.name}",
                state=HealthState.NEEDS_ATTENTION,
                detail=(
                    f"{key_file.name} has mode {oct(actual_mode)}, expected {oct(expected_mode)}"
                ),
                fix_type=FixType.AUTO,
                fix_command=f"chmod {oct(expected_mode)[2:]} ~/.ssh/{key_file.name}",
            )

        return CheckResult(
            category="permissions",
            check_id=check_id,
            label=f"SSH key: {key_file.name}",
            state=HealthState.NEEDS_ATTENTION,
            detail=(
                f"{key_file.name} has mode {oct(actual_mode)}, "
                f"expected {oct(expected_mode)} (not user-owned)"
            ),
            fix_type=FixType.COPY_PASTE,
            fix_command=f"chmod {oct(expected_mode)[2:]} ~/.ssh/{key_file.name}",
        )

    async def _check_aws_credentials_perms(self) -> CheckResult:
        """Check ~/.aws/credentials has mode 0o600 if it exists."""
        creds = Path.home() / ".aws" / "credentials"
        if not creds.exists():
            return CheckResult(
                category="permissions",
                check_id="perm_aws_credentials",
                label="AWS credentials permissions",
                state=HealthState.HEALTHY,
                detail="~/.aws/credentials does not exist — no check required",
                fix_type=FixType.NONE,
            )

        try:
            file_stat = creds.stat()
            actual_mode = stat.S_IMODE(file_stat.st_mode)
        except Exception as exc:
            return CheckResult(
                category="permissions",
                check_id="perm_aws_credentials",
                label="AWS credentials permissions",
                state=HealthState.NEEDS_ATTENTION,
                detail=f"Could not stat ~/.aws/credentials: {exc}",
                fix_type=FixType.NONE,
            )

        if actual_mode == 0o600:
            return CheckResult(
                category="permissions",
                check_id="perm_aws_credentials",
                label="AWS credentials permissions",
                state=HealthState.HEALTHY,
                detail="~/.aws/credentials has correct mode 0o600",
                fix_type=FixType.NONE,
            )

        try:
            user_owns = file_stat.st_uid == os.getuid()
        except Exception:
            user_owns = False

        if user_owns:
            self._fix_targets["perm_aws_credentials"] = (creds, 0o600)
            return CheckResult(
                category="permissions",
                check_id="perm_aws_credentials",
                label="AWS credentials permissions",
                state=HealthState.NEEDS_ATTENTION,
                detail=f"~/.aws/credentials has mode {oct(actual_mode)}, expected 0o600",
                fix_type=FixType.AUTO,
                fix_command="chmod 600 ~/.aws/credentials",
            )

        return CheckResult(
            category="permissions",
            check_id="perm_aws_credentials",
            label="AWS credentials permissions",
            state=HealthState.NEEDS_ATTENTION,
            detail=(
                f"~/.aws/credentials has mode {oct(actual_mode)}, expected 0o600 (not user-owned)"
            ),
            fix_type=FixType.COPY_PASTE,
            fix_command="chmod 600 ~/.aws/credentials",
        )

    async def _check_local_bin_writable(self) -> CheckResult:
        """Check ~/.local/bin is writable by the current user."""
        local_bin = Path.home() / ".local" / "bin"

        if not local_bin.exists():
            return CheckResult(
                category="permissions",
                check_id="perm_local_bin_writable",
                label="~/.local/bin writable",
                state=HealthState.RECOMMENDED,
                detail="~/.local/bin does not exist — create it to install user-scope tools",
                fix_type=FixType.COPY_PASTE,
                fix_command="mkdir -p ~/.local/bin",
            )

        if os.access(local_bin, os.W_OK):
            return CheckResult(
                category="permissions",
                check_id="perm_local_bin_writable",
                label="~/.local/bin writable",
                state=HealthState.HEALTHY,
                detail="~/.local/bin is writable",
                fix_type=FixType.NONE,
            )

        return CheckResult(
            category="permissions",
            check_id="perm_local_bin_writable",
            label="~/.local/bin writable",
            state=HealthState.NEEDS_ATTENTION,
            detail="~/.local/bin exists but is not writable by the current user",
            fix_type=FixType.COPY_PASTE,
            fix_command="chmod u+w ~/.local/bin",
        )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _unwrap_results(
        raw: list[Any],
        category: str,
        fallback_prefix: str,
    ) -> list[CheckResult]:
        """Convert asyncio.gather results (including exceptions) to CheckResult list."""
        results: list[CheckResult] = []
        for i, item in enumerate(raw):
            if isinstance(item, CheckResult):
                results.append(item)
            elif isinstance(item, BaseException):
                results.append(
                    CheckResult(
                        category=category,
                        check_id=f"{fallback_prefix}_{i}",
                        label="Check error",
                        state=HealthState.NEEDS_ATTENTION,
                        detail=f"Check raised an exception: {item}",
                        fix_type=FixType.NONE,
                    )
                )
        return results
