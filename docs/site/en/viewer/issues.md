# Issues & 3D Pins

## Creating an Issue

1. Select an element.
2. Click "New Issue" in the bottom Issue panel and fill in the title (required) and a comment.
3. The current camera view and a canvas screenshot are captured automatically on creation; the Issue appears in the list and a 3D pin is overlaid on the element.

## Status flow

`open` → `checking` → `resolved`, switchable in the list. Issue ids are `i_` plus 12 lowercase hex characters.

## 3D pins

- Each Issue with an entityId has an HTML pin projected in real time onto the element's position; it hides automatically when the element is invisible or the pin is off-screen.
- Clicking a pin or a list entry restores the camera view captured at creation, selects the element and highlights the Issue.

## Change history

The bottom panel has two tabs: "Issues / Change history". Change history shows the change log (time, entity, field, old → new, author) in reverse chronological order; with the direct-edit chain retired and the property panel read-only, this tab mainly serves historical review.

## API contract

Issue CRUD and screenshot static serving are covered in [Viewer REST API](/en/reference/rest-api).
