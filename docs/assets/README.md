# Documentation Assets

This directory contains visual assets for the documentation.

## Expected Images

### Screenshots
- `screenshot_light.png` / `screenshot_dark.png` - Main product screenshot (800px+ width)
- `feature_X_light.png` / `feature_X_dark.png` - Feature-specific screenshots
- `example_N_light.png` / `example_N_dark.png` - Example output visualizations

### Diagrams
- `architecture_light.png` / `architecture_dark.png` - System architecture diagram
- `workflow_light.png` / `workflow_dark.png` - Workflow/process diagrams

## Recommendations

- **Dimensions**: Minimum 800px width for screenshots
- **Format**: PNG for screenshots, SVG for diagrams when possible
- **Theme variants**: Provide both light and dark versions with `_light` and `_dark` suffixes
- **Optimization**: Compress images to keep repository size manageable

## Usage in Documentation

Reference images in markdown using theme-switching picture tags:

```markdown
<p align="center">
  <picture>
    <source media="(prefers-color-scheme: light)" srcset="assets/screenshot_light.png">
    <source media="(prefers-color-scheme: dark)" srcset="assets/screenshot_dark.png">
    <img src="assets/screenshot_light.png" alt="Description" width="800">
  </picture>
</p>
```
