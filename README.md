# Extract VST chunk_data from OBS

This script automatically locates and extracts the `chunk_data` for the **ReaFIR (reafir_standalone.dll)** plugin from OBS Studio scene JSON files.

Its primary purpose is to make it easy to retrieve ReaFIR noise-reduction configurations without manually finding and extractingg the value from the file.

## What This Script Does

- Scans the OBS scenes directory for `.json` files
- Allows selection of a scene file (or auto-selects if only only 1 exists)
- Recursively searches the JSON structure for ReaFIR VST filters
- Extracts the associated `chunk_data` value(s)
- Copies the chunk data to the clipboard (only if one instance is found)