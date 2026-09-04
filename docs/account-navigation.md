# Shared account navigation

Client account pages already use `templates/base.html`, which renders the shared LumisPixel navbar, account dropdown, responsive navigation, and `partials/sidebar.html`.

The photographer **My Profile** page intentionally uses the same base shell. It does not render the photographer workspace (`lpw`) sidebar. This keeps person-level account/profile surfaces consistent whether the same user is acting as a client, photographer, studio owner, or studio member.

Photographer business/workspace pages continue to use `photographer_workspace/base.html` because their navigation is workspace-specific.
