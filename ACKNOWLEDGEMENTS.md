# Format references

The format readers are included in this repository; no other local repository is
required to run them. Their existing format references are recorded here:

- BigWorld packed XML: [chirimenmonster/wotmods-tools XmlUnpacker](https://github.com/chirimenmonster/wotmods-tools/blob/master/utils/XmlUnpacker.py).
- Replay containers and event streams: [Monstrofil/replays_unpack replay_reader](https://github.com/Monstrofil/replays_unpack/blob/master/replay_unpack/replay_reader.py).
- Packet framing and health events: [wotto-wiki packet stream](https://intelliagent.gitlab.io/wotto-wiki/format/packet-stream/)
  and [health updates](https://intelliagent.gitlab.io/wotto-wiki/packets/packet08/subtype04/).

The main GUI uses only the Python standard library. Optional research tools use
SciPy, cryptography and xdis under their respective licenses; their code and game
resources are not redistributed in this source release.
