using System;
using System.Globalization;
using NetMQ;
using NetMQ.Sockets;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class QuestTelemetryHud : MonoBehaviour
{
    public string host = "192.168.1.18";
    public int port = 10012;
    public Transform trackingSpace;
    private SubscriberSocket subscriber;
    private TextMeshProUGUI[] labels;
    private Image[] fills;
    private float[] angles = new float[7];
    private int receivedFrames;
    private readonly float[] lowerLimits = { -2.8973f, -1.7628f, -2.8973f, -3.0718f, -2.8973f, -0.0175f, -2.8973f };
    private readonly float[] upperLimits = {  2.8973f,  1.7628f,  2.8973f, -0.0698f,  2.8973f,  3.7525f,  2.8973f };

    private void Start()
    {
        AsyncIO.ForceDotNet.Force();
        subscriber = new SubscriberSocket();
        subscriber.Connect($"tcp://{host}:{port}");
        subscriber.Subscribe("joint_angles");
        BuildHud();
        Debug.Log($"QUEST_HUD_READY tcp://{host}:{port}");
    }

    private void BuildHud()
    {
        var canvasObject = new GameObject("PandaJointLimitHUD");
        Transform view = Camera.main != null ? Camera.main.transform : trackingSpace;
        canvasObject.transform.SetParent(view, false);
        canvasObject.transform.localPosition = new Vector3(-0.34f, 0.04f, 0.72f);
        canvasObject.transform.localRotation = Quaternion.identity;
        canvasObject.transform.localScale = Vector3.one * 0.001f;
        var canvas = canvasObject.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.WorldSpace;
        canvasObject.AddComponent<CanvasScaler>().dynamicPixelsPerUnit = 10;
        canvasObject.AddComponent<GraphicRaycaster>();
        var panel = canvasObject.AddComponent<Image>();
        panel.color = new Color(0.02f, 0.03f, 0.06f, 0.82f);
        var rect = canvasObject.GetComponent<RectTransform>();
        rect.sizeDelta = new Vector2(330f, 410f);

        labels = new TextMeshProUGUI[7];
        fills = new Image[7];
        for (int i = 0; i < 7; i++)
        {
            var row = new GameObject($"J{i + 1}");
            row.transform.SetParent(canvasObject.transform, false);
            var rowRect = row.AddComponent<RectTransform>();
            rowRect.anchorMin = new Vector2(0.06f, 0.87f - i * 0.12f);
            rowRect.anchorMax = new Vector2(0.94f, 0.97f - i * 0.12f);
            rowRect.offsetMin = rowRect.offsetMax = Vector2.zero;
            var label = row.AddComponent<TextMeshProUGUI>();
            label.fontSize = 28;
            label.color = Color.white;
            label.text = $"J{i + 1} 0.00  [{lowerLimits[i]:0.0}, {upperLimits[i]:0.0}]";
            labels[i] = label;
            var fillObject = new GameObject("Fill");
            fillObject.transform.SetParent(row.transform, false);
            var fillRect = fillObject.AddComponent<RectTransform>();
            fillRect.anchorMin = new Vector2(0.45f, 0.15f);
            fillRect.anchorMax = new Vector2(0.95f, 0.35f);
            fillRect.offsetMin = fillRect.offsetMax = Vector2.zero;
            var image = fillObject.AddComponent<Image>();
            image.color = Color.green;
            fills[i] = image;
        }
    }

    private void Update()
    {
        if (subscriber == null) return;
        while (subscriber.TryReceiveFrameString(TimeSpan.Zero, out string frame))
        {
            var separator = frame.IndexOf(' ');
            if (separator < 0) continue;
            var values = frame.Substring(separator + 1).Trim('[', ']').Split(',');
            for (int i = 0; i < Math.Min(7, values.Length); i++)
                float.TryParse(values[i], NumberStyles.Float, CultureInfo.InvariantCulture, out angles[i]);
            receivedFrames++;
            if (receivedFrames == 1)
                Debug.Log("QUEST_HUD_FIRST_JOINT_FRAME");
        }
        if (labels == null) return;
        for (int i = 0; i < 7; i++)
        {
            var ratio = Mathf.InverseLerp(lowerLimits[i], upperLimits[i], angles[i]);
            var edgeDistance = Mathf.Min(ratio, 1f - ratio) * 2f;
            labels[i].text = $"J{i + 1} {angles[i]:0.00}  [{lowerLimits[i]:0.0}, {upperLimits[i]:0.0}]";
            fills[i].color = edgeDistance < 0.1f ? Color.red : edgeDistance < 0.3f ? Color.yellow : Color.green;
            fills[i].rectTransform.anchorMax = new Vector2(0.45f + 0.5f * ratio, 0.35f);
        }
    }

    private void OnDestroy()
    {
        subscriber?.Dispose();
        NetMQConfig.Cleanup(false);
    }
}
