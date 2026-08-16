"""User onboarding agent (deterministic).

Rule: for every person in ``context["invites"]``, invite (create) the user
in dairy-backend unless a user with that email already exists. When the invite
includes ``role_codes``, the agent resolves them to role ids via the roles
catalogue and grants them at creation.

Optional context flags:
- ``execute: false`` — record intended invites without calling action tools.
- ``default_role_codes`` — roles to grant when an invite lists none.
"""

from __future__ import annotations

from typing import Any

from app.agents.base import (
    STATUS_COMPLETED,
    STATUS_NOOP,
    AgentResult,
    AgentStep,
    BaseAgent,
    _extract_items,
)
from app.utils.helpers import get_logger

logger = get_logger("onboarding_agent")


class UserOnboardingAgent(BaseAgent):
    """Invite new users and grant initial roles."""

    id = "onboarding"
    name = "User Onboarding Agent"
    description = "Invites new users to the organization and grants their initial roles."
    tool_ids = (
        "identity.users",
        "identity.roles",
        "identity.user_invite",
    )
    required_permissions = ("user:manage",)

    async def run(self, context: dict[str, Any]) -> AgentResult:
        execute = bool(context.get("execute", True))
        self._steps = []

        invites = context.get("invites") or []
        if not invites:
            return self._result(STATUS_NOOP, "No user invites to process")

        role_map = await self._role_map(default_codes=context.get("default_role_codes"))
        existing = await self._existing_emails()

        invited = 0
        for invite in invites:
            email = str(invite.get("email") or "").strip().lower()
            if not email:
                continue
            label = f"invite user {email}"
            if email in existing:
                self._steps.append(
                    AgentStep("identity.user_invite", label, "skipped", "user already exists")
                )
                continue
            role_ids = self._resolve_role_ids(invite.get("role_codes"), role_map)
            if not execute:
                self._steps.append(
                    AgentStep(
                        "identity.user_invite",
                        label,
                        "skipped",
                        {"mode": "propose", "role_ids": role_ids},
                    )
                )
                continue
            try:
                await self._call(
                    "identity.user_invite",
                    body={
                        "email": email,
                        "password": str(invite.get("password") or "DairyAI@123"),
                        "first_name": str(invite.get("first_name") or ""),
                        "last_name": str(invite.get("last_name") or ""),
                        "phone": invite.get("phone"),
                        "employee_id": invite.get("employee_id"),
                        "timezone": invite.get("timezone"),
                        "language": invite.get("language"),
                        "role_ids": role_ids,
                    },
                    action=label,
                )
            except Exception:
                logger.warning("invite failed")
                self._steps.append(
                    AgentStep("identity.user_invite", label, "error", "invite rejected")
                )
                continue
            invited += 1

        logger.info("onboarding agent")
        actionable = [
            s
            for s in self._steps
            if s.tool_id == "identity.user_invite"
            and (s.status in ("ok", "error") or isinstance(s.detail, dict))
        ]
        if not actionable:
            return self._result(STATUS_NOOP, "No new users to invite")
        return self._result(
            STATUS_COMPLETED,
            f"Invited {invited} user(s) out of {len(invites)} requested",
        )

    async def _role_map(self, default_codes: Any) -> dict[str, str]:
        """Return ``{role_code: role_id}`` for the platform role catalogue."""
        try:
            payload = await self._call("identity.roles", action="fetch role catalogue")
        except Exception:
            logger.warning("could not fetch roles; invites will carry no roles")
            return {}
        role_map = {
            str(role.get("business_code") or role.get("code") or ""): str(role.get("id") or "")
            for role in _extract_items(payload)
        }
        if default_codes:
            default_codes = default_codes if isinstance(default_codes, list) else [default_codes]
            for code in default_codes:
                role_map.setdefault(str(code), "")
        return role_map

    async def _existing_emails(self) -> set[str]:
        """Return the emails of users already in the organization."""
        try:
            payload = await self._call("identity.users", action="fetch existing users")
        except Exception:
            logger.warning("could not list users; assuming none exist")
            return set()
        return {str(user.get("email") or "").strip().lower() for user in _extract_items(payload)}

    def _resolve_role_ids(self, codes: Any, role_map: dict[str, str]) -> list[str]:
        """Map role codes from an invite to role ids via the catalogue."""
        if not codes:
            return []
        codes = codes if isinstance(codes, list) else [codes]
        return [role_map[str(code)] for code in codes if str(code) in role_map]
