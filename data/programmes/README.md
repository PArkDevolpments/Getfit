# Getfit approved programme content

This directory is reserved for versioned programme content that has been explicitly approved for Getfit.

## Authority and validation rules

- Programme files are prescription authority. They must never be generated merely to fill a 52-week calendar.
- Each approved week must contain exactly four training days and pass the same strict schema and whole-week validator.
- Unknown fields fail validation rather than being ignored.
- Strength target/load semantics use the canonical Getfit programme domain models.
- Treadmill and spin-bike fields remain equipment-specific. A spin bike has no speed or incline prescription.
- Person overrides must reference an exercise that actually exists in that approved week and remain person scoped.
- Missing weeks, targets, loads, speeds or resistances remain missing until approved material is supplied.

## Current approved content

The existing production-shaped Foundation Week 1 remains in:

`programme_seed/home-workout-12m-v1/week-01.json`

Task 7 validates that file through `hwa.programmes` and the existing Foundation database importer. Its approved Day 4 conditioning structure is contract-frozen.

No Week 2–52 files are added here until their programme material is explicitly approved. Future batches should use a versioned directory such as `data/programmes/getfit-52-week-v1/` and must pass the same contract suite before merge.
