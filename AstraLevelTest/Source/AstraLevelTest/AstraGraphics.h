#pragma once

class UWorld;

/** Standalone rendering profiles; editor and PIE viewports are left untouched. */
struct FAstraGraphics
{
    static void Apply(UWorld* World);
};
