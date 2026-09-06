# Episode Naming

TV Manager 15 uses the naming pattern imported from SickChill's `[General] naming_pattern` setting when `rename_episodes` is enabled.

## Tokens

| Token | Meaning | Example |
| --- | --- | --- |
| `%SN` | Show name | `The Example Show` |
| `%S` | Season | `1` |
| `%0S` | Zero-padded season | `01` |
| `%E` | Episode sequence | `1E2` |
| `%0E` | Zero-padded episode sequence | `01E02` |
| `%EN` | Episode name(s) | `Pilot + Part Two` |

For a multi-episode source representing episodes 1 and 2, the pattern `S%0SE%0E` becomes `S01E01E02`.

## Windows safety

The naming engine replaces invalid Windows filename characters and protects reserved names such as `CON`, `AUX`, `NUL`, `COM1`, and `LPT1`.

## Associated files

When `move_associated_files` is enabled, recognized sidecar files beginning with the original media stem follow the renamed media file. Language suffixes are retained; for example:

`Show.S01E01.en.srt` → `My Show - S01E01 - Pilot.en.srt`
