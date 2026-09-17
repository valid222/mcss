from django.core.management.base import BaseCommand

from apps.custom_fields.models import CustomField, CustomFieldGroup

# (entity, key, label, is_sensitive, required) — needed by the self-service
# Staff Onboarding form (apps.staff_onboarding), which writes into these at
# approval time via the same masked-field display path that already covers
# bank account numbers. Both required per the original spec ("they will
# also be asked to provide their NIN number, qualification"). Ungrouped —
# left exactly where a Super Admin's own edits (if any) put them.
FIELDS = [
    ("staff", "nin", "NIN", True, True),
    ("staff", "qualification", "Qualification", False, True),
]

# The "Biodata" Data Title (apps.custom_fields.CustomFieldGroup) and the
# fields under it — only created when missing, so a school that already set
# these up by hand through Forms & Custom Fields is never overwritten or
# duplicated (get_or_create matches on entity+name for the group, entity+key
# for each field, same as FIELDS above). Renders identically on the Staff
# Registration form and the self-service/admin profile editors — one
# definition, no per-screen field list to keep in sync. "First/Middle/Last
# Name" replace the old hardcoded Full Name box; the frontend derives
# full_name from them automatically (see dynamicFieldOverrides.js) so
# nothing is ever asked for twice.
BIODATA_GROUP = ("staff", "Biodata")
BIODATA_FIELDS = [
    # key, label, field_type, required, placeholder
    ("first_name", "First Name", "text", True, "Enter first name"),
    ("middle_name", "Middle Name", "text", False, "Enter middle name"),
    ("last_name", "Last Name", "text", True, "Enter last name"),
    ("date_of_birth", "Date of Birth", "date", True, "Select date of birth"),
    ("email", "Email", "text", True, "Enter email address"),
    ("phone", "Phone", "text", True, "Enter phone number"),
    ("address", "Address", "text", True, "Enter residential address"),
    ("town_city", "Town/City", "text", True, "Enter town or city"),
    # field_type stays "text" in the DB, same as account_type/sort_code below
    # — the frontend (dynamicFieldOverrides.js) renders these as proper
    # State -> LGA cascading dropdowns from a bundled Nigeria dataset rather
    # than the Super Admin having to hand-enter ~774 LGA options here.
    ("state", "State", "text", True, "Select state"),
    ("lga", "LGA", "text", True, "Select LGA"),
]


class Command(BaseCommand):
    help = "Seeds default custom fields the app expects to exist (safe to run on every deploy — only creates rows that don't exist yet)."

    def handle(self, *args, **options):
        created = 0
        for entity, key, label, is_sensitive, required in FIELDS:
            _, was_created = CustomField.objects.get_or_create(
                entity=entity, key=key,
                defaults={"label": label, "field_type": "text", "is_sensitive": is_sensitive, "required": required},
            )
            created += int(was_created)

        entity, group_name = BIODATA_GROUP
        group, group_created = CustomFieldGroup.objects.get_or_create(entity=entity, name=group_name)
        created += int(group_created)
        for order, (key, label, field_type, required, placeholder) in enumerate(BIODATA_FIELDS):
            _, was_created = CustomField.objects.get_or_create(
                entity=entity, key=key,
                defaults={
                    "label": label, "field_type": field_type, "required": required,
                    "placeholder": placeholder, "group": group, "order": order,
                },
            )
            created += int(was_created)

        self.stdout.write(self.style.SUCCESS(f"Seeded {created} new custom field(s)/group(s)."))
