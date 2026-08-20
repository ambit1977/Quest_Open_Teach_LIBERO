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
    private readonly float[] limits = { 2.8973f, 1.7628f, 2.8973f, 3.0718f, 2.8973f, 0.0175f, 2.8973f };

    private void Start()
    {
        AsyncIO.ForceDotNet.Force();
        subscriber = new SubscriberSocket();
        subscriber.Connect($"tcp://{host}:{port}");
        subscriber.Subscribe("joint_angles");
        BuildHud();
    }

    private void BuildHud()
    {
        var canvasObject = new GameObject("PandaJointLimitHUD");
        canvasObject.transform.SetParent(trackingSpace ?? Camera.main.transform, false);
        canvasObject.transform.localPosition = new Vector3(0.42f, 0.22f, 0.8f);
        canvasObject.transform.localRotation = Quaternion.identity;
        var canvas = canvasObject.AddComponent<Canvas>();
        canvas.renderMode = RenderMode.WorldSpace;
        canvasObject.AddComponent<CanvasScaler>().dynamicPixelsPerUnit = 10;
        canvasObject.AddComponent<GraphicRaycaster>();
        var panel = canvasObject.AddComponent<Image>();
        panel.color = new Color(0.02f, 0.03f, 0.06f, 0.82f);
        var rect = canvasObject.GetComponent<RectTransform>();
        rect.sizeDelta = new Vector2(0.34f, 0.42f);

        labels = new TextMeshProUGUI[7];
        fills = new Image[7];
        for (int i = 0; i < 7; i++)
        {
            var row = new GameObject($"J{i + 1}");
            row.transform.SetParent(canvasObject.transform, false);
            var rowRect = row.AddComponent<RectTransform>();
            rowRect.anchorMin = new Vector2(0.06f, 0.88f - i * 0.12f);
            rowRect.anchorMax = new Vector2(0.94f, 0.98f - i * 0.12f);
            rowRect.offsetMin = rowRect.offsetMax = Vector2.zero;
            var label = row.AddComponent<TextMeshProUGUI>();
            label.fontSize = 5;
            label.color = Color.white;
            label.text = $"J{i + 1} 0.00 / ±{limits[i]:0.00}";
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
        }
        if (labels == null) return;
        for (int i = 0; i < 7; i++)
        {
            var ratio = Mathf.Clamp01(Mathf.Abs(angles[i]) / limits[i]);
            labels[i].text = $"J{i + 1} {angles[i]:0.00} / ±{limits[i]:0.00}";
            fills[i].color = ratio > 0.9f ? Color.red : ratio > 0.7f ? Color.yellow : Color.green;
            fills[i].rectTransform.anchorMax = new Vector2(0.45f + 0.5f * ratio, 0.35f);
        }
    }

    private void OnDestroy()
    {
        subscriber?.Dispose();
        NetMQConfig.Cleanup(false);
    }
}
