"""
Job Configuration Validator
Validates jobs.yaml configuration file using cerberus schema validation.
Can be used standalone or imported by scheduler.py.
"""
import yaml
from cerberus import Validator
from pathlib import Path

# Schema definition for job configuration
JOB_SCHEMA = {
    "jobs": {
        "type": "list",
        "schema": {
            "type": "dict",
            "schema": {
                "name": {"type": "string", "required": True},
                "command": {"type": "string", "required": True},
                "enabled": {"type": "boolean", "required": False, "default": True},
                "schedule": {
                    "type": "dict",
                    "schema": {
                        "every": {"type": "integer", "min": 1, "required": False},  # Not required for startup
                        "unit": {
                            "type": "string",
                            "allowed": ["seconds", "minutes", "hours", "days", "weeks", "months", "startup"],
                            "required": True
                        },
                        "at": {
                            "type": "string",
                            "regex": r"^(\d{2}:\d{2}|:\d{2})$",
                            "required": False
                        },
                        "day": {
                            "type": "string",
                            "allowed": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                            "required": False
                        },
                        "day_of_month": {
                            "type": "integer",
                            "min": 1,
                            "max": 31,
                            "required": False
                        }
                    },
                    "required": True
                }
            }
        }
    }
}

# Define which fields are valid for each schedule unit
VALID_FIELDS_BY_UNIT = {
    "seconds": {"every", "unit"},
    "minutes": {"every", "unit", "at"},
    "hours": {"every", "unit", "at"},
    "days": {"every", "unit", "at"},
    "weeks": {"every", "unit", "at", "day"},
    "months": {"unit", "at", "day_of_month"},
    "startup": {"unit"},
}

# Define which fields are required for each schedule unit
REQUIRED_FIELDS_BY_UNIT = {
    "seconds": {"every"},
    "minutes": {"every"},
    "hours": {"every"},
    "days": {"every"},
    "weeks": {"every"},
    "months": set(),  # day_of_month defaults to 1
    "startup": set(),
}


def validate_schedule_fields(jobs):
    """
    Validate that schedule fields are appropriate for the unit type.
    
    Args:
        jobs: List of job dictionaries
        
    Returns:
        list: List of warning/error messages (empty if all valid)
    """
    errors = []
    
    for job in jobs:
        name = job.get("name", "unknown")
        schedule = job.get("schedule", {})
        unit = schedule.get("unit")
        
        if not unit or unit not in VALID_FIELDS_BY_UNIT:
            continue  # Schema validation will catch this
        
        valid_fields = VALID_FIELDS_BY_UNIT[unit]
        required_fields = REQUIRED_FIELDS_BY_UNIT[unit]
        
        # Check for irrelevant fields
        for field in schedule:
            if field not in valid_fields:
                errors.append(f"Job '{name}': field '{field}' is not used for '{unit}' schedules")
        
        # Check for missing required fields
        for field in required_fields:
            if field not in schedule:
                errors.append(f"Job '{name}': field '{field}' is required for '{unit}' schedules")
    
    return errors


def validate_config(config_path="jobs.yaml", strict=True):
    """
    Validate job configuration file.
    
    Args:
        config_path: Path to jobs.yaml file (string or Path)
        strict: If True, reject irrelevant fields for schedule type
        
    Returns:
        dict: Validated configuration data
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If YAML syntax is invalid
        ValueError: If config doesn't match schema
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path) as f:
        data = yaml.safe_load(f)
    
    if data is None:
        raise ValueError("Configuration file is empty")
    
    validator = Validator(JOB_SCHEMA)
    if not validator.validate(data):
        raise ValueError(f"Invalid configuration:\n{validator.errors}")
    
    # Additional strict validation for field relevance
    if strict:
        field_errors = validate_schedule_fields(data.get("jobs", []))
        if field_errors:
            raise ValueError("Invalid configuration:\n" + "\n".join(field_errors))
    
    return data


def validate_and_print(config_path="jobs.yaml", strict=True):
    """
    Validate configuration and print result (for CLI usage).
    
    Args:
        config_path: Path to jobs.yaml file
        strict: If True, reject irrelevant fields
        
    Returns:
        dict: Validated configuration data, or None if invalid
    """
    try:
        data = validate_config(config_path, strict=strict)
        print(f"[OK] YAML config is valid. ({len(data.get('jobs', []))} jobs)")
        return data
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return None
    except yaml.YAMLError as e:
        print(f"[ERROR] YAML syntax error: {e}")
        return None
    except ValueError as e:
        print(f"[ERROR] {e}")
        return None


# CLI entry point
if __name__ == "__main__":
    import sys
    config_file = sys.argv[1] if len(sys.argv) > 1 else "jobs.yaml"
    result = validate_and_print(config_file)
    sys.exit(0 if result else 1)
