"""
Seed data for the BAS experiment catalogue.

Activity labels are the vocabulary the HAR model and FSM share; the `title`
field carries the crew-facing wording the UI displays.
"""
from typing import Any, Dict, List

SEED_EXPERIMENTS: List[Dict[str, Any]] = [
    {
        "code": "SIH-EXP-26174",
        "title": "On-board Dual-Box Handling & Verification",
        "description": "SIH 2026 Problem Statement 26174 baseline: retrieval and return validation of red and secondary inner boxes from outer container.",
        "category": "Astronaut BAS Experiment",
        "environment": "Microgravity",
        "estimated_duration": "00:15:00",
        "steps": [
            {
                "title": "Retrieve Red Box",
                "expected_activity": "RETRIEVE_RED_BOX",
                "description": "Remove the red inner box from the payload outer container.",
                "safety_critical": True,
            },
            {
                "title": "Retrieve Second Coloured Box",
                "expected_activity": "RETRIEVE_SECOND_COLORED_BOX",
                "description": "Remove the second coloured box from the payload outer container.",
                "safety_critical": True,
            },
            {
                "title": "Return Red Box",
                "expected_activity": "RETURN_RED_BOX",
                "description": "Return and secure the red box into the payload container slot.",
                "safety_critical": True,
            },
            {
                "title": "Return Second Coloured Box",
                "expected_activity": "RETURN_SECOND_COLORED_BOX",
                "description": "Return the second coloured box into the outer container to conclude procedure.",
                "safety_critical": True,
            },
        ],
    },
    {
        "code": "BAS-EXP-001",
        "title": "Microgravity Sample Handling",
        "description": "Controlled sample preparation and transfer sequence for BAS laboratory operations.",
        "category": "Materials Science",
        "environment": "Microgravity",
        "estimated_duration": "02:15:00",
        "steps": [
            {
                "title": "Prepare Experiment Container",
                "expected_activity": "PICK_CONTAINER",
                "description": "Retrieve and inspect the sealed experiment container from the storage rack.",
                "safety_critical": True,
            },
            {
                "title": "Open Container",
                "expected_activity": "OPEN_CONTAINER",
                "description": "Carefully open the container lid, ensuring no debris enters the sample chamber.",
                "safety_critical": True,
            },
            {
                "title": "Transfer Sample",
                "expected_activity": "POUR_SAMPLE",
                "description": "Use the precision gripper to transfer the biological sample into the analysis tray.",
                "safety_critical": True,
            },
            {
                "title": "Mix Sample",
                "expected_activity": "MIX_SAMPLE",
                "description": "Activate the automated mixing protocol for homogeneous sample distribution.",
                "safety_critical": False,
            },
            {
                "title": "Secure Container",
                "expected_activity": "CLOSE_CONTAINER",
                "description": "Seal the container and return it to the storage rack for post-experiment analysis.",
                "safety_critical": True,
            },
        ],
    },
    {
        "code": "BAS-EXP-002",
        "title": "Fluid Behavior Observation",
        "description": "Surface-tension and fluid behaviour study under sustained microgravity.",
        "category": "Fluid Dynamics",
        "environment": "Microgravity",
        "estimated_duration": "01:45:00",
        "steps": [
            {
                "title": "Initialize Fluid Cell",
                "expected_activity": "PICK_CONTAINER",
                "description": "Mount the fluid cell on the observation platform.",
                "safety_critical": False,
            },
            {
                "title": "Inject Test Fluid",
                "expected_activity": "POUR_SAMPLE",
                "description": "Inject the test fluid into the observation chamber.",
                "safety_critical": True,
            },
            {
                "title": "Record Behavior",
                "expected_activity": "MIX_SAMPLE",
                "description": "Capture high-speed video of fluid surface tension behaviour.",
                "safety_critical": False,
            },
            {
                "title": "Archive Data",
                "expected_activity": "PLACE_CONTAINER",
                "description": "Transfer recorded data to the station data storage system.",
                "safety_critical": False,
            },
        ],
    },
    {
        "code": "BAS-EXP-003",
        "title": "Biological Sample Study",
        "description": "Cell culture growth study with periodic imaging and preservation.",
        "category": "Biology",
        "environment": "Microgravity",
        "estimated_duration": "03:00:00",
        "steps": [
            {
                "title": "Prepare Culture Medium",
                "expected_activity": "PICK_CONTAINER",
                "description": "Prepare the sterile culture medium for cell growth.",
                "safety_critical": True,
            },
            {
                "title": "Inoculate Samples",
                "expected_activity": "POUR_SAMPLE",
                "description": "Inoculate the culture medium with the biological samples.",
                "safety_critical": True,
            },
            {
                "title": "Incubate",
                "expected_activity": "PLACE_CONTAINER",
                "description": "Place samples in the controlled-temperature incubation chamber.",
                "safety_critical": False,
            },
            {
                "title": "Monitor Growth",
                "expected_activity": "MIX_SAMPLE",
                "description": "Periodically image and measure cell culture growth patterns.",
                "safety_critical": False,
            },
            {
                "title": "Preserve Samples",
                "expected_activity": "CLOSE_CONTAINER",
                "description": "Preserve the samples for post-flight genetic analysis.",
                "safety_critical": True,
            },
        ],
    },
    {
        "code": "BAS-EXP-004",
        "title": "Crystal Growth Experiment",
        "description": "Slow-cooling protein crystal growth with thermal gradient monitoring.",
        "category": "Materials Science",
        "environment": "Microgravity",
        "estimated_duration": "04:30:00",
        "steps": [
            {
                "title": "Prepare Solution",
                "expected_activity": "PICK_CONTAINER",
                "description": "Mix the precursor solution for crystal growth.",
                "safety_critical": False,
            },
            {
                "title": "Initiate Growth",
                "expected_activity": "OPEN_CONTAINER",
                "description": "Begin the slow-cooling crystal growth protocol.",
                "safety_critical": True,
            },
            {
                "title": "Monitor Temperature",
                "expected_activity": "MIX_SAMPLE",
                "description": "Track temperature gradients across the growth chamber.",
                "safety_critical": False,
            },
            {
                "title": "Harvest Crystals",
                "expected_activity": "POUR_SAMPLE",
                "description": "Carefully extract grown crystals from the solution.",
                "safety_critical": True,
            },
            {
                "title": "Store Samples",
                "expected_activity": "PLACE_CONTAINER",
                "description": "Store harvested crystals in protective containers.",
                "safety_critical": False,
            },
            {
                "title": "Seal Storage",
                "expected_activity": "CLOSE_CONTAINER",
                "description": "Seal the storage container and log the sample inventory.",
                "safety_critical": True,
            },
        ],
    },
    {
        "code": "BAS-EXP-005",
        "title": "Thermal Conductivity Measurement",
        "description": "Heat-pulse thermal conductivity measurement of candidate materials.",
        "category": "Physics",
        "environment": "Microgravity",
        "estimated_duration": "02:00:00",
        "steps": [
            {
                "title": "Calibrate Sensors",
                "expected_activity": "PICK_CONTAINER",
                "description": "Calibrate the thermal sensors against known reference values.",
                "safety_critical": False,
            },
            {
                "title": "Mount Sample",
                "expected_activity": "PLACE_CONTAINER",
                "description": "Mount the test material on the measurement platform.",
                "safety_critical": False,
            },
            {
                "title": "Apply Heat Pulse",
                "expected_activity": "MIX_SAMPLE",
                "description": "Apply a controlled heat pulse and measure the response.",
                "safety_critical": True,
            },
            {
                "title": "Record Data",
                "expected_activity": "CLOSE_CONTAINER",
                "description": "Record thermal conductivity measurements for analysis.",
                "safety_critical": False,
            },
        ],
    },
    {
        "code": "BAS-EXP-006",
        "title": "Plant Seed Germination Study",
        "description": "Seed germination and seedling development study in microgravity.",
        "category": "Biology",
        "environment": "Microgravity",
        "estimated_duration": "06:00:00",
        "steps": [
            {
                "title": "Prepare Seed Pads",
                "expected_activity": "PICK_CONTAINER",
                "description": "Prepare the nutrient-infused seed germination pads.",
                "safety_critical": False,
            },
            {
                "title": "Plant Seeds",
                "expected_activity": "POUR_SAMPLE",
                "description": "Place seeds in the germination chamber on prepared pads.",
                "safety_critical": False,
            },
            {
                "title": "Monitor Germination",
                "expected_activity": "MIX_SAMPLE",
                "description": "Image and measure seed germination progress daily.",
                "safety_critical": False,
            },
            {
                "title": "Harvest Seedlings",
                "expected_activity": "CLOSE_CONTAINER",
                "description": "Harvest seedlings and preserve for genetic analysis.",
                "safety_critical": True,
            },
        ],
    },
]
