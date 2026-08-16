"""Tool registry: the backend endpoint invocations agents may use.

Each tool maps 1:1 to a real dairy-backend REST endpoint (double
authorization — the backend remains the final authority on every action).
The ``required_capability`` field mirrors a ``dairy_platform`` permission
code (e.g. ``Planning.Review``); it is documented now and will be enforced
by the governance layer in the approvals phase.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


class RiskLevel(str, enum.Enum):
    """Risk classification used for governance/approval decisions."""

    READ = "read"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class Tool:
    """A single backend endpoint invocation capability."""

    id: str
    name: str
    description: str
    method: str
    path: str  # backend path; may contain {param} placeholders
    required_capability: str  # dairy_platform permission code, e.g. "Planning.Review"
    risk_level: RiskLevel = RiskLevel.LOW
    requires_approval: bool = False  # Phase 2 governance flag (default off for MVP)
    body_schema: dict[str, str] = field(default_factory=dict)  # field name -> description


# ---------------------------------------------------------------------------
# Tool catalogue (paths target dairy-backend's /api/v1 routes)
# ---------------------------------------------------------------------------

TOOLS: tuple[Tool, ...] = (
    # --- Reads ---
    Tool(
        id="inventory.low_stock",
        name="Low-stock items",
        description="List inventory items below their restock threshold.",
        method="GET",
        path="/api/v1/inventory/low-stock",
        required_capability="Inventory.View",
        risk_level=RiskLevel.READ,
    ),
    Tool(
        id="planning.list",
        name="List plans",
        description="List planning batches and manifests, optionally by status.",
        method="GET",
        path="/api/v1/planning",
        required_capability="Planning.View",
        risk_level=RiskLevel.READ,
    ),
    Tool(
        id="planning.detail",
        name="Plan detail",
        description="Fetch a single planning batch by id.",
        method="GET",
        path="/api/v1/planning/{planning_id}",
        required_capability="Planning.View",
        risk_level=RiskLevel.READ,
    ),
    Tool(
        id="planning.manifest",
        name="Manifest detail",
        description="Fetch the manifest of a planning batch (includes the manifest id).",
        method="GET",
        path="/api/v1/planning/{planning_id}/manifest",
        required_capability="Planning.View",
        risk_level=RiskLevel.READ,
    ),
    Tool(
        id="assignment.list",
        name="List assignments",
        description="List delivery assignments, optionally by status.",
        method="GET",
        path="/api/v1/assignments",
        required_capability="Assignment.View",
        risk_level=RiskLevel.READ,
    ),
    Tool(
        id="collections.outstanding",
        name="Outstanding list",
        description="List outstanding balances, optionally filtered to overdue.",
        method="GET",
        path="/api/v1/outstanding",
        required_capability="Outstanding.View",
        risk_level=RiskLevel.READ,
    ),
    Tool(
        id="collections.exceptions",
        name="Collection exceptions",
        description="List collection exceptions.",
        method="GET",
        path="/api/v1/exceptions",
        required_capability="Collection.View",
        risk_level=RiskLevel.READ,
    ),
    # --- Planning actions ---
    Tool(
        id="planning.review",
        name="Review manifest",
        description="Review a generated manifest (moves it to awaiting_approval).",
        method="POST",
        path="/api/v1/planning/{planning_id}/review",
        required_capability="Planning.Review",
        risk_level=RiskLevel.MEDIUM,
        body_schema={"notes": "Optional reviewer notes."},
    ),
    Tool(
        id="planning.approve",
        name="Approve manifest",
        description="Approve a reviewed manifest.",
        method="POST",
        path="/api/v1/planning/{planning_id}/approve",
        required_capability="Planning.Approve",
        risk_level=RiskLevel.MEDIUM,
        body_schema={"notes": "Optional approver notes."},
    ),
    Tool(
        id="planning.regenerate",
        name="Regenerate plan",
        description="Regenerate quantities for a planning batch.",
        method="POST",
        path="/api/v1/planning/{planning_id}/regenerate",
        required_capability="Planning.Regenerate",
        risk_level=RiskLevel.MEDIUM,
        body_schema={"notes": "Optional regeneration notes."},
    ),
    Tool(
        id="planning.cancel",
        name="Cancel plan",
        description="Cancel a planning batch.",
        method="POST",
        path="/api/v1/planning/{planning_id}/cancel",
        required_capability="Planning.Cancel",
        risk_level=RiskLevel.MEDIUM,
        body_schema={"reason": "Cancellation reason."},
    ),
    # --- Assignment actions ---
    Tool(
        id="assignment.assign",
        name="Assign delivery",
        description="Assign an approved manifest to delivery staff.",
        method="POST",
        path="/api/v1/assignments/assign",
        required_capability="Assignment.Create",
        risk_level=RiskLevel.HIGH,
        body_schema={
            "manifest_id": "Approved manifest to assign.",
            "assigned_staff_id": "Delivery staff user to assign.",
            "delivery_session": "Session: MORNING / EVENING / BOTH.",
            "notes": "Optional notes.",
        },
    ),
    Tool(
        id="assignment.accept",
        name="Accept assignment",
        description="Accept an assigned manifest as delivery staff.",
        method="POST",
        path="/api/v1/assignments/{assignment_id}/accept",
        required_capability="Assignment.Accept",
        risk_level=RiskLevel.MEDIUM,
    ),
    # --- Execution actions ---
    Tool(
        id="execution.start",
        name="Start execution",
        description="Start a supply execution for an accepted assignment (creates the visit plan).",
        method="POST",
        path="/api/v1/execution/start",
        required_capability="Execution.Start",
        risk_level=RiskLevel.HIGH,
        body_schema={"assignment_id": "ACCEPTED or IN_PROGRESS assignment to execute."},
    ),
    # --- Inventory actions ---
    Tool(
        id="inventory.stock_in",
        name="Stock in",
        description="Record a stock-in movement for a SKU.",
        method="POST",
        path="/api/v1/inventory/stock-in",
        required_capability="Inventory.RecordMovement",
        risk_level=RiskLevel.HIGH,
        body_schema={
            "sku_id": "SKU to replenish.",
            "quantity": "Quantity received (Decimal).",
            "unit": "Inventory unit, e.g. liters.",
            "source": "Stock-in source, e.g. supplier.",
            "reference_number": "Optional source reference.",
            "notes": "Optional notes.",
            "effective_date": "ISO date of the movement.",
        },
    ),
    Tool(
        id="inventory.adjust",
        name="Adjust inventory",
        description="Correct a SKU's available quantity.",
        method="POST",
        path="/api/v1/inventory/{sku_id}/adjust",
        required_capability="Inventory.Update",
        risk_level=RiskLevel.HIGH,
        body_schema={
            "adjustment_quantity": "Signed quantity delta.",
            "reason": "Adjustment reason.",
            "notes": "Optional notes.",
            "effective_date": "ISO date of the adjustment.",
        },
    ),
    # --- Collections actions ---
    Tool(
        id="collections.collect",
        name="Record collection",
        description="Record a payment/collection from a retailer.",
        method="POST",
        path="/api/v1/collections/collect",
        required_capability="Collection.Create",
        risk_level=RiskLevel.HIGH,
        body_schema={
            "retailer_id": "Retailer paying.",
            "amount": "Collection amount (Decimal).",
            "payment_method": "Payment method used.",
            "reference_number": "Optional payment reference.",
            "notes": "Optional notes.",
            "delivery_execution_id": "Optional linked supply execution.",
        },
    ),
    Tool(
        id="collections.verify",
        name="Verify collection",
        description="Verify a recorded collection.",
        method="POST",
        path="/api/v1/collections/{collection_id}/verify",
        required_capability="Collection.Verify",
        risk_level=RiskLevel.MEDIUM,
        body_schema={"notes": "Optional verification notes."},
    ),
    Tool(
        id="collections.adjust_outstanding",
        name="Adjust outstanding",
        description="Adjust a retailer's outstanding balance.",
        method="POST",
        path="/api/v1/outstanding/{outstanding_id}/adjust",
        required_capability="Outstanding.Manage",
        risk_level=RiskLevel.HIGH,
        body_schema={
            "adjustment_amount": "Signed amount to add to outstanding.",
            "reason": "Adjustment reason.",
            "reference_collection_id": "Optional linked collection.",
        },
    ),
    Tool(
        id="exceptions.detect",
        name="Detect exception",
        description="Raise a collection exception for a retailer.",
        method="POST",
        path="/api/v1/exceptions",
        required_capability="CollectionException.Acknowledge",
        risk_level=RiskLevel.MEDIUM,
        body_schema={
            "retailer_id": "Retailer the exception belongs to.",
            "exception_type": "Exception type, e.g. overdue_account.",
            "description": "Exception description.",
            "amount": "Optional amount involved.",
        },
    ),
    Tool(
        id="exceptions.resolve",
        name="Resolve exception",
        description="Resolve an open collection exception.",
        method="POST",
        path="/api/v1/exceptions/{exception_id}/resolve",
        required_capability="CollectionException.Resolve",
        risk_level=RiskLevel.MEDIUM,
        body_schema={"resolution_notes": "Optional resolution notes."},
    ),
    Tool(
        id="exceptions.close",
        name="Close exception",
        description="Close a resolved collection exception.",
        method="POST",
        path="/api/v1/exceptions/{exception_id}/close",
        required_capability="CollectionException.Close",
        risk_level=RiskLevel.MEDIUM,
        body_schema={"closing_notes": "Optional closing notes."},
    ),
    # --- Identity / onboarding ---
    Tool(
        id="identity.users",
        name="List users",
        description="List users of the organization, optionally by status.",
        method="GET",
        path="/api/v1/users",
        required_capability="Users.View",
        risk_level=RiskLevel.READ,
    ),
    Tool(
        id="identity.user_detail",
        name="User detail",
        description="Fetch a single user by id.",
        method="GET",
        path="/api/v1/users/{user_id}",
        required_capability="Users.View",
        risk_level=RiskLevel.READ,
    ),
    Tool(
        id="identity.roles",
        name="List roles",
        description="List platform roles available for assignment.",
        method="GET",
        path="/api/v1/roles",
        required_capability="Roles.View",
        risk_level=RiskLevel.READ,
    ),
    Tool(
        id="identity.permissions",
        name="List permissions",
        description="List platform permissions.",
        method="GET",
        path="/api/v1/permissions",
        required_capability="Permissions.View",
        risk_level=RiskLevel.READ,
    ),
    Tool(
        id="identity.user_roles",
        name="User roles",
        description="List the roles assigned to a user.",
        method="GET",
        path="/api/v1/resolve/roles/{user_id}",
        required_capability="Roles.View",
        risk_level=RiskLevel.READ,
    ),
    Tool(
        id="identity.user_invite",
        name="Invite user",
        description="Invite (create) a user in the organization with initial roles.",
        method="POST",
        path="/api/v1/users",
        required_capability="Users.Create",
        risk_level=RiskLevel.HIGH,
        body_schema={
            "email": "Invitee email address.",
            "password": "Initial password for the invited user.",
            "first_name": "Invitee first name.",
            "last_name": "Invitee last name.",
            "phone": "Optional phone number.",
            "employee_id": "Optional employee id.",
            "timezone": "Optional timezone.",
            "language": "Optional language.",
            "role_ids": "Role ids to grant on creation.",
            "organization_id": "Optional organization id (defaults to caller org).",
        },
    ),
    Tool(
        id="identity.user_role_assign",
        name="Assign role",
        description="Assign a role to an existing user.",
        method="POST",
        path="/api/v1/users/{user_id}/roles",
        required_capability="Roles.Assign",
        risk_level=RiskLevel.HIGH,
        body_schema={
            "role_id": "Role to assign.",
            "organization_id": "Organization scope for the role.",
        },
    ),
    Tool(
        id="identity.user_activate",
        name="Activate user",
        description="Reactivate a deactivated user.",
        method="POST",
        path="/api/v1/users/{user_id}/activate",
        required_capability="Users.Update",
        risk_level=RiskLevel.MEDIUM,
    ),
    Tool(
        id="identity.user_deactivate",
        name="Deactivate user",
        description="Deactivate a user account.",
        method="POST",
        path="/api/v1/users/{user_id}/deactivate",
        required_capability="Users.Suspend",
        risk_level=RiskLevel.MEDIUM,
    ),
    Tool(
        id="identity.user_suspend",
        name="Suspend user",
        description="Suspend a user account.",
        method="POST",
        path="/api/v1/users/{user_id}/suspend",
        required_capability="Users.Suspend",
        risk_level=RiskLevel.HIGH,
        body_schema={"reason": "Suspension reason."},
    ),
    Tool(
        id="identity.user_reactivate",
        name="Reactivate user",
        description="Reactivate a suspended user.",
        method="POST",
        path="/api/v1/users/{user_id}/reactivate",
        required_capability="Users.Update",
        risk_level=RiskLevel.MEDIUM,
    ),
)


class ToolRegistry:
    """Lookup registry over the static tool catalogue."""

    def __init__(self, tools: tuple[Tool, ...] = TOOLS) -> None:
        self._tools: dict[str, Tool] = {tool.id: tool for tool in tools}

    def get(self, tool_id: str) -> Tool:
        """Return the tool with ``tool_id`` or raise ``KeyError``."""
        return self._tools[tool_id]

    def list_tools(self) -> list[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def all_ids(self) -> list[str]:
        """Return all tool ids, sorted."""
        return sorted(self._tools)

    def by_capability(self, capability: str) -> list[Tool]:
        """Return tools requiring a given ``dairy_platform`` permission code."""
        return [tool for tool in self._tools.values() if tool.required_capability == capability]


tool_registry = ToolRegistry()
