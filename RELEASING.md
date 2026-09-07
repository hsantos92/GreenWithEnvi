# Releasing GreenWithEnvi

Releases belong to [hsantos92/GreenWithEnvi](https://github.com/hsantos92/GreenWithEnvi/releases).
The native NVML changes are currently documented under **Unreleased**.

1. Run the checks in [NVML-MIGRATION.md](NVML-MIGRATION.md) and build native resources.
2. Verify the GTK window, About credits, project links and desktop launcher.
   Record hardware control testing separately from mocked regression results.
3. Choose a version and update `APP_VERSION` in `gwe/conf.py`.
4. Move the relevant Unreleased changelog entries into a dated release section
   and add matching release metadata to `data/com.leinardi.gwe.appdata.xml`.
5. Check that README branch instructions match the branch being released.
6. Commit the release preparation, create the version tag, and push the commit
   and tag when ready to publish.
7. Create a GitHub Release for that tag with the changelog entries, native launch
   instructions, tested hardware and known limitations.

The old Flathub build-bot and GitLab release workflow do not publish this fork.
Do not advertise Flatpak controls until the packaging and authorization path
have been migrated and validated.
