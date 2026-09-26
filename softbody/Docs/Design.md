# Softbody design

## Outcome
UE 5.7 project in `softbody`: the third person template Manny walks around a studio and interacts with three deformable balls. The 6.7 cm tennis ball and 13.4 cm double ball are gripped from above by the right hand. The 1 metre ball is pushed and compressed by the character's body.

## Implementation
- Use Epic's installed 5.7 mannequin, animation and materials at their original `/Game/Characters` paths.
- Native third person character, procedural arm IK and finger joints. Contacts come from the displayed hand bones.
- A CPU XPBD surface solver preserves signed volume, resists stretching, resolves contact spheres and restores the sphere. This is a custom soft body solver, not a Chaos Flesh asset.
- A procedural mesh displays deformed particles and smooth normals. Two studio stands support the small balls. The large ball uses a moving Chaos rigid core and a deformable surface, with a world-aligned solver frame.
- E rests the palm on a small ball/leaves interaction. Wheel adjusts persistent finger curl; mouse down/up increases/releases vertical pressure; mouse left/right slides the contact point in screen space. Each control is independent. LMB temporarily squeezes fully, then returns to the wheel setting. C switches inspection view; R resets hand controls and ball; Tab demonstrates repeated squeeze/release. Nonzero manual input takes over from the current demo pose.

## Verification
Compile with the installed UE 5.7.4 toolchain. Run automation tests for stability, contact deformation, recovery and large frame deltas. Build the saved map in Unreal. Run a rendered interaction and inspect actual screenshots and runtime measurements.

## Boundaries
The two small balls have fixed resting centers. The large ball translates and bounces; rigid rotation is locked to keep its solver floor horizontal. No pickup/throw, network play or arbitrary mesh simulation. Existing sibling projects stay intact.
