# Softbody Implementation Plan

**Goal:** Create the requested working UE 5.7 third person soft ball scene.
**Architecture:** Native character drives hand bone contacts into a fixed timestep soft surface solver. A procedural mesh renders the solved positions in a saved studio map.
**Tech stack:** UE 5.7.4, C++, Unreal Python, native automation tests.
**Spec:** Design.md

## Work items
- [x] Solver: test rest, contact deformation, recovery and long frames; implement constraints in SoftBodySolver.
- [x] Character: template movement, arm IK, finger grip, actual bone contacts, camera and interaction input.
- [x] Scene: create materials and a saved L_SoftbodyLab with studio lighting and three ball stations.
- [x] Integration: project scaffold, procedural ball actor, game mode, HUD, launch script.
- [x] Verification: compile, four passing automation tests, scene validation, runtime squeeze/release report and screenshots.

## Review focus
Release clears every contact. Contacts use ball local coordinates. High frame delta cannot explode simulation. Enter/exit leaves movement usable. Displayed hand and physical contacts coincide. Template assets and saved startup map load without missing packages.
