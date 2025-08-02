# How to Create a 'Compie' Image for your Plugin.

To generate an image of 'Compie' for use in the AgentUp plugin registry, you can use the following prompt with an image generation model. I found so far ChatGPT works best.

```plaintext
Create a high-quality 2D digital illustration in a modern rubber hose + retro cartoon style, featuring an anthropomorphic vintage computer (CRT monitor with a keyboard as body and gloved hands/feet).

The character should have a friendly expression and be interacting with a themed object (e.g., holding a camera, map, wrench, etc.) depending on the topic.

Use a limited vintage-inspired color palette: muted teal, beige, off-white, faded red, and dark outlines.

Include bold, distressed sans-serif lettering above and below the character, with the top word(s) indicating the app or brand (e.g., "AGENTUP") and the bottom word(s) indicating the tool name (e.g., "IMAGE", "SYS TOOLS", or “MAPS", “SLACK”).

The background should be transparent or a light textured paper tone if transparency isn’t possible.

The overall style should be playful, bold, clean, and ideal for branding, badges, or banners.

The image dimensions must be 400x400, with an alpha channel to provide a transparent background
The theme for the image should be:

[Description of Compie]
```

You will often find the dimensions get ignored, if this is the case you can resize to 400x400 in an image editing application
such as Gimp, or Photoshop.

Once oyou have your image, move it into the `static` folder in your plugin directory and name it `logo.png`

```
.
├── static
│   └── logo.png
```