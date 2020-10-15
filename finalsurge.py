# Create new workout
# POST https://beta.finalsurge.com/api/Data?request=WorkoutLibraryWorkoutAdd
json_payload = {
    "wlib_key": "0b629a36-f20b-4dba-bbe2-e14c98b049ac",
    "name": "!Name!",
    "description": "!Description!",
    "code": "!Code!",
    "activity_type_key": "00000001-0001-0001-0001-000000000001",
    "activity_type_name": "Run",
    "activity_sub_type_key": "",
    "activity_sub_type_name": "",
    "planned_duration": 3723,
    "planned_amount": 11,
    "planned_amount_type": "mi",
}

# Workout steps
# POST https://beta.finalsurge.com/api/Data?request=WorkoutLibraryBuilderSave
# &scope=USER&scopekey=123a8bc7-3911-4960-9b79-dfaa163c69b2&wlib_workout_key=73877658-343f-4a3a-a9d2-4a78f2d47f5f
json_payload = {
    "target_options": [
        {
            "name": "!Name!",
            "sport": "running",
            "steps": [
                {
                    "type": "step",
                    "id": 101,
                    "name": None,
                    "durationType": "TIME",
                    "duration": "1:00",
                    "targetAbsOrPct": "",
                    "durationDist": 0,
                    "data": [],
                    "distUnit": "mi",
                    "target": [
                        {
                            "targetType": "power",
                            "zoneBased": False,
                            "targetLow": "100",
                            "targetHigh": "200",
                            "targetOption": None,
                            "targetIsTimeBased": False,
                            "zone": 0,
                        },
                        {
                            "targetType": "open",
                            "zoneBased": False,
                            "targetLow": "0",
                            "targetHigh": "0",
                            "targetOption": "",
                            "targetIsTimeBased": False,
                            "zone": 0,
                        },
                    ],
                    "intensity": "WARMUP",
                    "comments": None,
                },
                {
                    "type": "repeat",
                    "name": None,
                    "id": 5001,
                    "data": [
                        {
                            "type": "step",
                            "id": 102,
                            "name": None,
                            "durationType": "TIME",
                            "duration": "1:00",
                            "targetAbsOrPct": "",
                            "durationDist": 0,
                            "data": [],
                            "distUnit": "mi",
                            "target": [
                                {
                                    "targetType": "power",
                                    "zoneBased": False,
                                    "targetLow": "200",
                                    "targetHigh": "300",
                                    "targetOption": None,
                                    "targetIsTimeBased": False,
                                    "zone": 0,
                                },
                                {
                                    "targetType": "open",
                                    "zoneBased": False,
                                    "targetLow": "0",
                                    "targetHigh": "0",
                                    "targetOption": "",
                                    "targetIsTimeBased": False,
                                    "zone": 0,
                                },
                            ],
                            "intensity": "ACTIVE",
                            "comments": None,
                        },
                        {
                            "type": "step",
                            "id": 103,
                            "name": None,
                            "durationType": "TIME",
                            "duration": "2:00",
                            "targetAbsOrPct": "",
                            "durationDist": 0,
                            "data": [],
                            "distUnit": "mi",
                            "target": [
                                {
                                    "targetType": "power",
                                    "zoneBased": False,
                                    "targetLow": "300",
                                    "targetHigh": "400",
                                    "targetOption": None,
                                    "targetIsTimeBased": False,
                                    "zone": 0,
                                },
                                {
                                    "targetType": "open",
                                    "zoneBased": False,
                                    "targetLow": "0",
                                    "targetHigh": "0",
                                    "targetOption": "",
                                    "targetIsTimeBased": False,
                                    "zone": 0,
                                },
                            ],
                            "intensity": "REST",
                            "comments": None,
                        },
                    ],
                    "repeats": 2,
                    "durationType": "OPEN",
                    "comments": None,
                },
                {
                    "type": "step",
                    "id": 104,
                    "name": None,
                    "durationType": "TIME",
                    "duration": "1:30",
                    "targetAbsOrPct": "",
                    "durationDist": 0,
                    "data": [],
                    "distUnit": "mi",
                    "target": [
                        {
                            "targetType": "power",
                            "zoneBased": False,
                            "targetLow": "400",
                            "targetHigh": "500",
                            "targetOption": None,
                            "targetIsTimeBased": False,
                            "zone": 0,
                        },
                        {
                            "targetType": "open",
                            "zoneBased": False,
                            "targetLow": "0",
                            "targetHigh": "0",
                            "targetOption": "",
                            "targetIsTimeBased": False,
                            "zone": 0,
                        },
                    ],
                    "intensity": "COOLDOWN",
                    "comments": None,
                },
            ],
            "target": "power",
        }
    ],
    "target_override": None,
}


# List workout libraries
# GET https://beta.finalsurge.com/api/Data?request=WorkoutLibraryListEx&mine_only=false

# List Workouts
# GET https://beta.finalsurge.com/api/Data?request=WorkoutLibraryWorkoutList
