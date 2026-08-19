using System;
using System.Collections;
using System.Net.Sockets;
using System.Text;
using TMPro;
using UnityEngine;
using UnityEngine.UI;

public class QuestSimulatorLauncher : MonoBehaviour
{
    private const int LauncherPort = 8125;
    private readonly string[] stageNames =
    {
        "Top drawer",
        "Bottom drawer",
        "Bowl to drawer",
        "Open microwave",
        "Moka to stove",
        "Soup to basket",
        "Cheese to tray",
        "Book to shelf"
    };

    private NetworkManager networkManager;
    private GameObject launcherPanel;
    private TextMeshProUGUI stageText;
    private TextMeshProUGUI statusText;
    private int selectedStage = 3;

    [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
    private static void Bootstrap()
    {
        GameObject host = new GameObject("QuestSimulatorLauncher");
        DontDestroyOnLoad(host);
        host.AddComponent<QuestSimulatorLauncher>();
    }

    private IEnumerator Start()
    {
        GameObject menuCanvas = null;
        while (menuCanvas == null || networkManager == null)
        {
            menuCanvas = FindSceneObject("MenuCanvas");
            GameObject networkObject = GameObject.Find("NetworkConfigsLoader");
            if (networkObject != null)
                networkManager = networkObject.GetComponent<NetworkManager>();
            yield return null;
        }

        BuildMenu(menuCanvas.transform);
        // Opening the Quest app from the system App Library should be enough
        // to bring up the default LIBERO stage on the Mac. The Mac launcher
        // treats this as a no-op when a simulator is already running.
        yield return new WaitForSeconds(0.5f);
        SendCommand("start");
    }

    private static GameObject FindSceneObject(string objectName)
    {
        foreach (GameObject candidate in Resources.FindObjectsOfTypeAll<GameObject>())
        {
            if (candidate.name == objectName && candidate.scene.IsValid())
                return candidate;
        }
        return null;
    }

    private void BuildMenu(Transform menuCanvas)
    {
        Button openButton = CreateButton(
            menuCanvas,
            "SimulatorButton",
            "Simulator",
            new Vector2(15.1f, -1.5f),
            new Vector2(9f, 4f),
            new Color(0.12f, 0.45f, 0.70f, 1f)
        );

        launcherPanel = CreatePanel(menuCanvas);
        launcherPanel.SetActive(false);
        openButton.onClick.AddListener(() => launcherPanel.SetActive(true));
    }

    private GameObject CreatePanel(Transform parent)
    {
        GameObject panel = new GameObject("SimulatorLauncherPanel", typeof(RectTransform), typeof(Image));
        panel.layer = 5;
        panel.transform.SetParent(parent, false);
        RectTransform panelRect = panel.GetComponent<RectTransform>();
        panelRect.anchoredPosition = Vector2.zero;
        panelRect.sizeDelta = new Vector2(40f, 21f);
        panel.GetComponent<Image>().color = new Color(0.04f, 0.07f, 0.10f, 0.98f);

        CreateText(panel.transform, "Title", "LIBERO Simulator", new Vector2(0f, 8f), new Vector2(34f, 2.5f), 1.8f);
        stageText = CreateText(panel.transform, "StageText", "", new Vector2(0f, 4.5f), new Vector2(26f, 3f), 1.45f);

        Button previous = CreateButton(panel.transform, "PreviousStage", "<", new Vector2(-16f, 4.5f), new Vector2(4f, 3.5f), new Color(0.22f, 0.27f, 0.32f, 1f));
        Button next = CreateButton(panel.transform, "NextStage", ">", new Vector2(16f, 4.5f), new Vector2(4f, 3.5f), new Color(0.22f, 0.27f, 0.32f, 1f));
        previous.onClick.AddListener(() => ChangeStage(-1));
        next.onClick.AddListener(() => ChangeStage(1));

        Button start = CreateButton(panel.transform, "StartSimulator", "Start", new Vector2(-12f, 0f), new Vector2(9f, 4f), new Color(0.12f, 0.56f, 0.30f, 1f));
        Button restart = CreateButton(panel.transform, "RestartSimulator", "Restart", new Vector2(0f, 0f), new Vector2(9f, 4f), new Color(0.90f, 0.52f, 0.10f, 1f));
        Button stop = CreateButton(panel.transform, "StopSimulator", "Stop", new Vector2(12f, 0f), new Vector2(9f, 4f), new Color(0.72f, 0.18f, 0.18f, 1f));
        start.onClick.AddListener(() => SendCommand("start"));
        restart.onClick.AddListener(() => SendCommand("restart"));
        stop.onClick.AddListener(() => SendCommand("stop"));

        statusText = CreateText(panel.transform, "Status", "Mac must be awake", new Vector2(0f, -4f), new Vector2(32f, 2.5f), 1.25f);
        Button back = CreateButton(panel.transform, "Back", "Back", new Vector2(0f, -7.5f), new Vector2(9f, 3.5f), new Color(0.22f, 0.27f, 0.32f, 1f));
        back.onClick.AddListener(() => panel.SetActive(false));

        RefreshStageText();
        return panel;
    }

    private void ChangeStage(int direction)
    {
        selectedStage = ((selectedStage - 1 + direction + stageNames.Length) % stageNames.Length) + 1;
        RefreshStageText();
    }

    private void RefreshStageText()
    {
        if (stageText != null)
            stageText.text = "Stage " + selectedStage + ": " + stageNames[selectedStage - 1];
    }

    private void SendCommand(string command)
    {
        string host = networkManager != null && networkManager.netConfig != null
            ? networkManager.netConfig.IPAddress
            : "";
        if (String.IsNullOrEmpty(host) || host == "undefined")
        {
            if (statusText != null)
                statusText.text = "Set Mac IP first";
            return;
        }

        string requestId = Guid.NewGuid().ToString("N");
        string payload = "{\"id\":\"" + requestId + "\",\"command\":\"" + command + "\",\"stage\":" + selectedStage + "}";
        byte[] data = Encoding.UTF8.GetBytes(payload);

        try
        {
            using (UdpClient client = new UdpClient())
            {
                for (int index = 0; index < 3; index++)
                    client.Send(data, data.Length, host, LauncherPort);
            }
            Debug.Log("QUEST_LAUNCHER_COMMAND_SENT command=" + command + " stage=" + selectedStage + " host=" + host);
            if (statusText != null)
                statusText.text = command.Substring(0, 1).ToUpper() + command.Substring(1) + " sent for Stage " + selectedStage;
        }
        catch (Exception exception)
        {
            Debug.LogError("Quest launcher command failed: " + exception);
            if (statusText != null)
                statusText.text = "Send failed";
        }
    }

    private static GameObject CreatePanelObject(Transform parent, string name, Vector2 position, Vector2 size)
    {
        GameObject item = new GameObject(name, typeof(RectTransform));
        item.layer = 5;
        item.transform.SetParent(parent, false);
        RectTransform rect = item.GetComponent<RectTransform>();
        rect.anchoredPosition = position;
        rect.sizeDelta = size;
        return item;
    }

    private static Button CreateButton(Transform parent, string name, string label, Vector2 position, Vector2 size, Color color)
    {
        GameObject item = CreatePanelObject(parent, name, position, size);
        Image image = item.AddComponent<Image>();
        image.color = color;
        Button button = item.AddComponent<Button>();
        button.targetGraphic = image;

        TextMeshProUGUI text = CreateText(item.transform, "Label", label, Vector2.zero, size, 1.35f);
        text.raycastTarget = false;
        return button;
    }

    private static TextMeshProUGUI CreateText(Transform parent, string name, string value, Vector2 position, Vector2 size, float fontSize)
    {
        GameObject item = CreatePanelObject(parent, name, position, size);
        TextMeshProUGUI text = item.AddComponent<TextMeshProUGUI>();
        text.text = value;
        text.fontSize = fontSize;
        text.alignment = TextAlignmentOptions.Center;
        text.color = Color.white;
        text.enableWordWrapping = false;
        return text;
    }
}
