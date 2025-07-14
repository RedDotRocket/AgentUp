#!/bin/bash
# Clean up template test output directories

echo "🧹 Cleaning up template test output..."

# Remove common test output directories
rm -rf rendered rendered-* *_rendered test-render custom-render

# Remove any context files
rm -f *-context.json custom-context.json

echo "✓ Cleanup complete!"
echo "These directories are also gitignored for future runs"