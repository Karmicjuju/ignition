from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from textual.widgets import Button, Static

from ignition.app import IgnitionApp
from ignition.core.state import save_state
from ignition.schemas.auth import AwsAuthState, AwsProfile, ProfileType
from ignition.schemas.state import AppStateModel
from ignition.ui.screens.auth import AuthScreen
from ignition.ui.screens.home import HomeScreen


def _complete_state() -> AppStateModel:
    return AppStateModel(install_id="test-id", onboarding_complete=True)


def _empty_auth_state() -> AwsAuthState:
    return AwsAuthState(
        profiles=[],
        active_profile=None,
        session_expiry=None,
        last_checked=datetime.now(UTC),
    )


def _populated_auth_state() -> AwsAuthState:
    return AwsAuthState(
        profiles=[
            AwsProfile(
                name="sso-dev",
                type=ProfileType.SSO,
                region="us-east-1",
                sso_start_url="https://example.awsapps.com/start",
                is_active=True,
            ),
            AwsProfile(name="static-prod", type=ProfileType.STATIC, region="us-west-2"),
        ],
        active_profile="sso-dev",
        session_expiry=None,
        last_checked=datetime.now(UTC),
    )


async def _navigate_to_auth(pilot: object) -> AuthScreen:  # type: ignore[type-arg]
    await pilot.pause()  # type: ignore[attr-defined]
    await pilot.press("ctrl+a")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]
    screen = pilot.app.screen  # type: ignore[attr-defined]
    assert isinstance(screen, AuthScreen)
    return screen


# ---------------------------------------------------------------------------
# Boot / navigation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_screen_boots(isolated_paths: Path) -> None:
    """ctrl+a from HomeScreen must push AuthScreen."""
    save_state(_complete_state())

    with patch(
        "ignition.core.auth.AuthService.load_auth_state",
        new_callable=AsyncMock,
    ) as mock_load:
        mock_load.return_value = _empty_auth_state()
        async with IgnitionApp(demo_mode=False).run_test() as pilot:
            await pilot.pause()
            assert isinstance(pilot.app.screen, HomeScreen)
            await pilot.press("ctrl+a")
            await pilot.pause()
            assert isinstance(pilot.app.screen, AuthScreen)


# ---------------------------------------------------------------------------
# Empty-state CTA copy (UX Decision #15)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_profiles_state_points_at_repair_button(isolated_paths: Path) -> None:
    """When no profiles are detected the loading-msg Static must
    surface the Repair Config CTA copy — not a dead-end label."""
    save_state(_complete_state())

    with patch(
        "ignition.core.auth.AuthService.load_auth_state",
        new_callable=AsyncMock,
    ) as mock_load:
        mock_load.return_value = _empty_auth_state()
        async with IgnitionApp(demo_mode=False).run_test() as pilot:
            screen = await _navigate_to_auth(pilot)
            # Allow the on_mount @work to complete
            await pilot.pause(delay=0.3)

            loading = screen.query_one("#loading-msg", Static)
            rendered = str(loading.render())
            assert "No AWS profiles found" in rendered
            assert "Repair Config" in rendered, (
                "Empty-state copy must explicitly name the Repair Config button"
            )

            # And the Repair Config button itself must remain available so
            # the CTA is actionable.
            repair_btn = screen.query_one("#btn-repair", Button)
            assert repair_btn.disabled is False


# ---------------------------------------------------------------------------
# Busy state (UX Decision #14, P1-3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_busy_state_disables_all_action_buttons(isolated_paths: Path) -> None:
    """While an action @work is running, all four action buttons must be
    disabled and the active button label must end with '…'.
    On completion the buttons must re-enable and labels must reset."""
    save_state(_complete_state())

    with patch(
        "ignition.core.auth.AuthService.load_auth_state",
        new_callable=AsyncMock,
    ) as mock_load:
        mock_load.return_value = _populated_auth_state()
        async with IgnitionApp(demo_mode=False).run_test() as pilot:
            screen = await _navigate_to_auth(pilot)
            await pilot.pause(delay=0.3)

            # Drive the busy state directly: avoids race conditions vs.
            # mocking the slow subprocess. The state machine is the unit
            # under test.
            screen._set_busy("btn-login")

            for btn_id in ("btn-login", "btn-refresh", "btn-switch", "btn-repair"):
                btn = screen.query_one(f"#{btn_id}", Button)
                assert btn.disabled is True, f"{btn_id} should be disabled while busy"

            login_btn = screen.query_one("#btn-login", Button)
            refresh_btn = screen.query_one("#btn-refresh", Button)
            assert str(login_btn.label).endswith("…"), "Active button must show working indicator"
            assert not str(refresh_btn.label).endswith("…"), (
                "Inactive buttons should not show the working indicator"
            )

            # Release.
            screen._set_busy(None)

            for btn_id in ("btn-login", "btn-refresh", "btn-switch", "btn-repair"):
                btn = screen.query_one(f"#{btn_id}", Button)
                assert btn.disabled is False, f"{btn_id} should re-enable after busy"
                assert not str(btn.label).endswith("…")


@pytest.mark.asyncio
async def test_button_press_during_busy_is_dropped(isolated_paths: Path) -> None:
    """on_button_pressed must drop events while _busy is True so the user
    cannot spam-queue subprocesses."""
    save_state(_complete_state())

    with (
        patch(
            "ignition.core.auth.AuthService.load_auth_state",
            new_callable=AsyncMock,
        ) as mock_load,
        patch(
            "ignition.core.auth.AuthService.repair_config",
            new_callable=AsyncMock,
        ) as mock_repair,
    ):
        mock_load.return_value = _populated_auth_state()
        mock_repair.return_value = (True, "ok")

        async with IgnitionApp(demo_mode=False).run_test() as pilot:
            screen = await _navigate_to_auth(pilot)
            await pilot.pause(delay=0.3)

            screen._busy = True

            initial_call_count = mock_repair.call_count
            repair_btn = screen.query_one("#btn-repair", Button)
            repair_btn.press()
            await pilot.pause(delay=0.2)

            assert mock_repair.call_count == initial_call_count, (
                "Press during busy must not invoke the service"
            )


# ---------------------------------------------------------------------------
# Switch-profile scope notice (UX Decision #13, P1-5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_switch_profile_consumes_tuple_and_notifies_scope(
    isolated_paths: Path,
) -> None:
    """The screen must consume the (state, scope_notice) tuple from
    AuthService.switch_profile and surface the notice to the user."""
    save_state(_complete_state())

    with (
        patch(
            "ignition.core.auth.AuthService.load_auth_state",
            new_callable=AsyncMock,
        ) as mock_load,
        patch(
            "ignition.core.auth.AuthService.switch_profile",
            new_callable=AsyncMock,
        ) as mock_switch,
    ):
        mock_load.return_value = _populated_auth_state()
        new_state = _populated_auth_state()
        mock_switch.return_value = (
            new_state,
            "Profile switched in Ignition only. Run `export AWS_PROFILE=foo`",
        )

        async with IgnitionApp(demo_mode=False).run_test() as pilot:
            screen = await _navigate_to_auth(pilot)
            await pilot.pause(delay=0.3)

            captured: list[tuple[str, str | None]] = []
            original_notify = screen.notify

            def _capture(
                msg: str,
                *args: object,
                severity: str | None = None,
                **kwargs: object,
            ) -> None:
                captured.append((msg, severity))
                # Forward to keep the screen behaviour intact.
                if severity is not None:
                    original_notify(msg, *args, severity=severity, **kwargs)
                else:
                    original_notify(msg, *args, **kwargs)

            # Stub _selected_profile so we don't depend on cursor row state.
            with (
                patch.object(screen, "notify", side_effect=_capture),
                patch.object(screen, "_selected_profile", return_value="sso-dev"),
            ):
                screen._action_switch()
                await pilot.pause(delay=0.3)

            assert mock_switch.await_count == 1
            switch_msgs = [(m, s) for (m, s) in captured if "Switched to profile" in m]
            assert switch_msgs, f"expected a switch notify; captured={captured}"
            switch_msg, severity = switch_msgs[0]
            assert "Ignition only" in switch_msg, (
                "Switch notify must include the Ignition-only scope caveat"
            )
            assert "export AWS_PROFILE" in switch_msg, (
                "Switch notify must include the shell-export remediation"
            )
            assert severity == "warning", (
                "Switch notify must use warning severity so the user reads "
                "it as actionable, not informational"
            )
