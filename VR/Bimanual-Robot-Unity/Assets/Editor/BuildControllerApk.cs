using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

public static class BuildControllerApk
{
    [MenuItem("Open Teach/Build Controller APK")]
    public static void Build()
    {
        const string packageName = "com.NYU.Bimanual.Controller";
        const string productName = "Open Teach LIBERO Controller";

        PlayerSettings.productName = productName;
        PlayerSettings.SetApplicationIdentifier(BuildTargetGroup.Android, packageName);
        PlayerSettings.bundleVersion = "1.3-controller";
        PlayerSettings.Android.bundleVersionCode = 4;
        PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
        PlayerSettings.SetScriptingBackend(
            BuildTargetGroup.Android,
            ScriptingImplementation.IL2CPP
        );

        if (!EditorUserBuildSettings.SwitchActiveBuildTarget(
                BuildTargetGroup.Android,
                BuildTarget.Android))
        {
            throw new InvalidOperationException("Failed to switch the active build target to Android.");
        }

        string[] scenes = EditorBuildSettings.scenes
            .Where(scene => scene.enabled)
            .Select(scene => scene.path)
            .ToArray();

        string outputPath = Path.GetFullPath(Path.Combine(
            Application.dataPath,
            "..",
            "..",
            "..",
            "build",
            "BimanualController.apk"
        ));

        Directory.CreateDirectory(Path.GetDirectoryName(outputPath));

        BuildReport report = BuildPipeline.BuildPlayer(new BuildPlayerOptions
        {
            scenes = scenes,
            locationPathName = outputPath,
            target = BuildTarget.Android,
            options = BuildOptions.None
        });

        if (report.summary.result != BuildResult.Succeeded)
        {
            throw new InvalidOperationException(
                $"Android build failed: {report.summary.result} " +
                $"({report.summary.totalErrors} errors)"
            );
        }

        Debug.Log(
            $"CONTROLLER_APK_BUILT path={outputPath} " +
            $"size={report.summary.totalSize} package={packageName}"
        );
    }
}
