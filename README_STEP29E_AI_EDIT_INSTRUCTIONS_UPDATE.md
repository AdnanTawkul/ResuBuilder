# Step 29E: AI Edit Instructions

This update adds a focused post-generation editing workflow to the Review page.

## Added

- New **AI edit instructions** section in the Review page.
- New **Apply AI Edit Instructions** button.
- Lets the user give targeted instructions such as:
  - move a skill to another section
  - focus more on specific experience
  - make the covering letter shorter
  - remove unsupported claims
  - change tone or emphasis
- The selected CV or covering letter is revised by the selected AI provider.
- Existing CV/covering-letter text is replaced only after the AI edit completes.
- Manual edit instructions are saved and restored in workspace JSON.
- Exported application snapshot includes the manual edit instructions.

## Test flow

1. Generate a CV or covering letter.
2. Open Review.
3. Select CV or Covering Letter.
4. Write specific instructions in **AI edit instructions**.
5. Click **Apply AI Edit Instructions**.
6. Confirm the revised document appears in Generate.
7. Run Quality Check again.
8. Save Workspace.
9. Close and reload workspace.
10. Confirm the instructions are restored.
