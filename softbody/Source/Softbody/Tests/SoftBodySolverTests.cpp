#include "../SoftBodySolver.h"

#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"

namespace SoftBodySolverTests
{
    constexpr float TestRadius = 18.0f;

    void Simulate(FSoftBodySolver& Solver, const TArray<FSoftBodyContact>& Contacts, int32 Frames)
    {
        for (int32 Frame = 0; Frame < Frames; ++Frame)
        {
            Solver.Advance(1.0f / 60.0f, Contacts, -Solver.GetRadius());
        }
    }

    bool HasFinitePositions(const FSoftBodySolver& Solver)
    {
        for (const FVector& Position : Solver.GetPositions())
        {
            if (Position.ContainsNaN() || Position.SizeSquared() > 1000000.0)
            {
                return false;
            }
        }
        return FMath::IsFinite(Solver.GetVolumeRatio());
    }
}

// Catches unstable rest forces, a missing floor, and a broken closed surface/volume constraint.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSoftBodyRestStabilityTest, "Softbody.Solver.RestStability",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSoftBodyRestStabilityTest::RunTest(const FString& Parameters)
{
    FSoftBodySolver Solver;
    Solver.Initialize(SoftBodySolverTests::TestRadius);
    TestTrue(TEXT("Surface has enough vertices for visible finger dents"), Solver.GetPositions().Num() >= 500);
    TestTrue(TEXT("Surface contains complete triangles"), Solver.GetTriangles().Num() >= 3000 && Solver.GetTriangles().Num() % 3 == 0);
    SoftBodySolverTests::Simulate(Solver, {}, 240);

    TestTrue(TEXT("Rest positions remain finite"), SoftBodySolverTests::HasFinitePositions(Solver));
    TestTrue(TEXT("Rest volume remains within five percent"), FMath::Abs(Solver.GetVolumeRatio() - 1.0f) < 0.05f);
    TestTrue(TEXT("Gravity causes only a small resting deformation"), Solver.GetMaxDisplacement() < 2.5f);
    TestEqual(TEXT("No hand contact at rest"), Solver.GetContactCount(), 0);
    for (const FVector& Position : Solver.GetPositions())
    {
        if (!TestTrue(TEXT("Surface remains above the floor"), Position.Z >= -SoftBodySolverTests::TestRadius - 0.001))
        {
            break;
        }
    }
    return true;
}

// Removing contact projection must fail the dent assertion; removing elastic recovery must fail release.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSoftBodyCompressionTest, "Softbody.Solver.ContactCompressionAndRecovery",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSoftBodyCompressionTest::RunTest(const FString& Parameters)
{
    FSoftBodySolver Solver;
    Solver.Initialize(SoftBodySolverTests::TestRadius);
    Solver.SetSoftness(0.75f);
    const TArray<FVector> RestPositions = Solver.GetPositions();
    TArray<FSoftBodyContact> Contacts;
    Contacts.Add({FVector(0.0, 0.0, 19.0), 7.0f});
    Contacts.Add({FVector(9.0, 0.0, 14.0), 5.0f});
    SoftBodySolverTests::Simulate(Solver, Contacts, 180);

    float TopInwardDisplacement = 0.0f;
    for (int32 Index = 0; Index < RestPositions.Num(); ++Index)
    {
        if (RestPositions[Index].Z > 17.0 && FMath::Abs(RestPositions[Index].X) < 4.0)
        {
            TopInwardDisplacement = FMath::Max(TopInwardDisplacement,
                static_cast<float>(RestPositions[Index].Z - Solver.GetPositions()[Index].Z));
        }
        for (const FSoftBodyContact& Contact : Contacts)
        {
            if (!TestTrue(TEXT("Surface vertices do not penetrate hand spheres"),
                FVector::Distance(Solver.GetPositions()[Index], Contact.Center) >= Contact.Radius - 0.01f))
            {
                return false;
            }
        }
    }
    TestTrue(TEXT("Contact makes a visible inward dent"), TopInwardDisplacement > 2.0f);
    TestTrue(TEXT("Contact is reported"), Solver.GetContactCount() > 0);
    TestTrue(TEXT("Held volume stays plausible"), Solver.GetVolumeRatio() > 0.78f && Solver.GetVolumeRatio() < 1.2f);
    TestTrue(TEXT("Held state remains finite"), SoftBodySolverTests::HasFinitePositions(Solver));
    const float HeldDisplacement = Solver.GetMaxDisplacement();

    SoftBodySolverTests::Simulate(Solver, {}, 240);
    TestTrue(TEXT("Release restores the surface"), Solver.GetMaxDisplacement() < HeldDisplacement * 0.35f);
    TestTrue(TEXT("Release restores volume"), FMath::Abs(Solver.GetVolumeRatio() - 1.0f) < 0.05f);
    TestEqual(TEXT("Released contact count clears"), Solver.GetContactCount(), 0);
    Solver.Reset();
    TestTrue(TEXT("Reset exactly restores the undeformed surface"), Solver.GetMaxDisplacement() < 0.0001f);
    return true;
}

// Catches an uncapped variable timestep or accumulated debt causing exploding positions after a hitch.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSoftBodyTimeStepTest, "Softbody.Solver.TimeStepSpikes",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSoftBodyTimeStepTest::RunTest(const FString& Parameters)
{
    FSoftBodySolver Solver;
    Solver.Initialize(SoftBodySolverTests::TestRadius);
    const TArray<FSoftBodyContact> Contacts = {{FVector(0.0, 0.0, 18.0), 6.0f}};
    const float TimeSteps[] = {0.0f, -0.01f, 0.5f, 1.0f / 240.0f, 2.0f, 1.0f / 30.0f};
    for (int32 Frame = 0; Frame < 60; ++Frame)
    {
        Solver.Advance(TimeSteps[Frame % UE_ARRAY_COUNT(TimeSteps)], Contacts, -SoftBodySolverTests::TestRadius);
    }
    TestTrue(TEXT("Hitches preserve finite positions"), SoftBodySolverTests::HasFinitePositions(Solver));
    TestTrue(TEXT("Hitches keep deformation bounded"), Solver.GetMaxDisplacement() < SoftBodySolverTests::TestRadius);
    TestTrue(TEXT("Hitches keep volume positive and bounded"), Solver.GetVolumeRatio() > 0.65f && Solver.GetVolumeRatio() < 1.35f);
    SoftBodySolverTests::Simulate(Solver, {}, 240);
    TestTrue(TEXT("Solver recovers after hitches"), Solver.GetMaxDisplacement() < 2.5f);
    return true;
}

// Catches world-unit gravity or constraint tuning that crushes small balls or prevents large balls deforming.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FSoftBodySizeTest, "Softbody.Solver.SizeIndependentElasticity",
    EAutomationTestFlags::EditorContext | EAutomationTestFlags::EngineFilter)

bool FSoftBodySizeTest::RunTest(const FString& Parameters)
{
    for (const float Radius : {3.35f, 6.7f, 50.0f})
    {
        FSoftBodySolver Solver;
        Solver.Initialize(Radius);
        SoftBodySolverTests::Simulate(Solver, {}, 180);
        TestTrue(TEXT("All sizes retain their resting shape"), Solver.GetMaxDisplacement() < Radius * 0.14f);
        const TArray<FSoftBodyContact> Contacts = {{FVector(0.0, 0.0, Radius * 1.05), Radius * 0.39f}};
        SoftBodySolverTests::Simulate(Solver, Contacts, 180);
        TestTrue(TEXT("All sizes visibly deform under contact"), Solver.GetMaxDisplacement() > Radius * 0.1f);
        TestTrue(TEXT("All sizes preserve held volume"), Solver.GetVolumeRatio() > 0.8f && Solver.GetVolumeRatio() < 1.2f);
        SoftBodySolverTests::Simulate(Solver, {}, 240);
        TestTrue(TEXT("All sizes recover after release"), Solver.GetMaxDisplacement() < Radius * 0.14f);
        TestTrue(TEXT("All sizes remain finite"), SoftBodySolverTests::HasFinitePositions(Solver));
    }
    return true;
}
#endif
