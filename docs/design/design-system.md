# Design System

## Page 1

Ignition: Design System
This document outlines the visual and interaction design guidelines for Ignition. It provides a shared
language for engineering and design teams to implement a cohesive look and feel that balances function
and personality.
1. Tone and Identity
Ignition should feel:
• Modern and technical – Clean lines, confident typography and crisp contrasts.
• Energetic and purposeful – Use Reactor‑themed language and subtle motion to convey power
without being gimmicky.
• Trustworthy and clear – Always prioritise clarity of message over theme; avoid jargon in critical
situations.
2. Colour Palette
Ignition defaults to a dark theme reminiscent of high‑contrast terminal environments, with an optional
light mode. Colours should be defined in variables for easy theming:
Token Dark Theme Light Theme Usage
background #0f1115 #f8f9fa Main background
surface #1a1c23 #ffffff Panels and cards
primary #6fd47e #227f40 Call to action, highlights
accent #44c7f4 #0077b6 Highlights, icons
danger #e74c3c #c0392b Errors, critical states
warning #f1c40f #f39c12 Warnings, caution
success #2ecc71 #27ae60 Success messages
text-primary #dfe4ea #1a1a1a Primary text
text-secondary #8f9bb3 #4d4d4d Secondary text
Accessibility
Ensure sufficient contrast between text and background. All colour combinations must meet WCAG AA
contrast ratios.
1

---

### Table 1 (Page 1)

| Token Dark Theme Light Theme Usage |
|---|
| background #0f1115 #f8f9fa Main background |
| surface #1a1c23 #ffffff Panels and cards |
| primary #6fd47e #227f40 Call to action, highlights |
| accent #44c7f4 #0077b6 Highlights, icons |
| danger #e74c3c #c0392b Errors, critical states |
| warning #f1c40f #f39c12 Warnings, caution |
| success #2ecc71 #27ae60 Success messages |
| text-primary #dfe4ea #1a1a1a Primary text |
| text-secondary #8f9bb3 #4d4d4d Secondary text |

## Page 2

3. Typography
Textual uses the terminal's fixed-width font; font size cannot be changed at the application level. Visual
hierarchy is achieved through weight, colour and markup rather than size. Apply a consistent style scale:
• Headline: bold, primary colour
• Subheadline: bold, text‑primary colour
• Body: regular, text‑primary colour
• Caption: regular, text‑secondary colour
4. Layout and Spacing
• Use a cell-based spacing scale (1, 2, 3, 4 cell increments) for padding and margins in TCSS.
• Use generous spacing around content in full mode; reduce padding in compact mode.
• Cards should use a visible border style (e.g. round or solid) to lift them off the background; Textual
does not support border-radius.
• Align text and icons consistently; avoid random offsets.
5. Motion and Animations
Ignition uses motion sparingly to guide the user. Transitions should be short (100–200 ms) and use easing
functions (e.g. ease‑in‑out). Respect the user’s motion preference: if reduced motion is enabled, disable
animations and provide instant state changes.
Common animations:
• Fade and slide for panel transitions.
• Progress bars that fill smoothly.
• Subtle pulsing of icons to indicate background activity.
6. Components
Panels and Cards
Panel containers house groups of related information (e.g. status, health, quick actions). Cards summarise
discrete items (e.g. tool descriptions). Use consistent margins and drop shadows.
Buttons
Buttons come in three styles: primary, secondary and tertiary. Primary buttons use the primary colour;
secondary buttons use a neutral surface with a coloured border; tertiary buttons are text links. Buttons
should have at least 3 rows of height and clear labels. All buttons must be keyboard-focusable and
activatable via Enter or Space.
Lists and Tables
Use lists for simple item selection and tables for tabular data. Keep tables narrow; avoid horizontal scrolling
by breaking information into multiple tables or using plain text. Do not place long sentences inside tables.
2

---

## Page 3

Forms
Application forms should include clear labels, placeholder hints and validation messages. Inline error messages
appear below fields in the danger colour.
Icons and Graphics
Use minimal line icons from a consistent icon set (e.g. Lucide). Accent colours may be applied to icons to
signify status (green for success, red for errors). Use decorative graphics sparingly and avoid distracting
backgrounds.
7. Density Modes
Ignition supports two density settings:
• Full – Suitable for new users and large terminals. Offers more whitespace, bigger cards and larger
fonts.
• Compact – Suitable for experienced users or smaller terminals. Reduces margins, condenses lists
and compresses panels vertically.
Switching density should not break the layout or require horizontal scrolling.
8. Themes and Personalisation
Users can choose dark or light mode. The theme is applied globally. Motion can be toggled off for users
with motion sensitivity. Density can be switched between compact and full. Accent colours are fixed per
theme to maintain a cohesive Reactor identity; user‑defined accents are out of scope for MVP.
9. Language and Tone Guidelines
Ignition uses Reactor‑themed phrases to enliven the experience. Examples include:
• Startup – “Initializing Reactor interface…”, “Charging core systems…”, “Ready.”
• Installation – “Charging runtime modules…”, “Synchronizing control surfaces…”.
• Success – “Core systems online.”, “Reactor output nominal.”
• Warnings – “Subsystem variance detected.”, “Calibration recommended.”
• Errors – “Access systems offline.”, followed by a clear explanation and actionable guidance.
Use these phrases judiciously; critical messages (e.g. error explanations) should prioritise plain language.
10. Accessibility and Internationalisation
• All text should be translatable; avoid hard‑coded strings.
• Provide tooltip labels and keyboard focus indicators on all interactive widgets.
• Ensure that colour alone is not the sole means of conveying information; accompany coloured
indicators with text or icons.
3

---

## Page 4

11. Future Considerations
As Ignition evolves to include more modules (e.g. repository management), the design system should
extend rather than be replaced. New components should adhere to spacing, colour and motion guidelines
described here. A living style guide or component library may be developed to support rapid iteration.
4

---
