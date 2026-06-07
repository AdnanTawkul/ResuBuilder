# Data Storage

ResuBuilder stores private user data locally and keeps it out of Git.

## Source run

When running from source:

```powershell
python app.py
```

Data is saved under the project root:

```text
data/
```

## Local packaged build

When running a development executable from:

```text
dist/ResuBuilder/ResuBuilder.exe
```

ResuBuilder still saves data under the project root:

```text
data/
```

This is intentional. It prevents user data from being lost when `build/` and `dist/` are deleted before rebuilding.

## Typical data files

```text
data/settings.json
data/candidate_profile.json
data/applications/*.json
data/logs/qt_gui.log
```

The default profile is saved as:

```text
data/candidate_profile.json
```

The app now uses one clear profile workflow:

```text
Load Profile...
Save Profile
Save Profile As...
```

`Load Profile...` can load the default saved profile or any other profile JSON file. This replaces the older separate import/export profile actions.

These files may contain private personal and job-application information. Do not commit them.
