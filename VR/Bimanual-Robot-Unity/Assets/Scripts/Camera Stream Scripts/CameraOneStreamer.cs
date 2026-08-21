using UnityEngine;
using UnityEngine.UI;

using NetMQ;
using NetMQ.Sockets;

using System;
using System.Collections;
using System.Threading;

public class CameraOneStreamer : MonoBehaviour
{
    private Thread imageStreamer;
    private Thread handImageStreamer;
    private byte[] latestImage;
    private byte[] latestHandImage;
    private volatile bool receiveRunning;
    private float nextTextureUpdate;
    private const float TextureUpdateInterval = 1f / 6f;

    public RawImage image;
    private RawImage handImage;
    private Texture2D texture;
    private Texture2D handTexture;

    //public NetworkConfigs netConf;
    private bool connectionEstablished = false;
    private string communicationAddress;
    private string handCommunicationAddress;
    private NetworkManager netConfig;

    private void StartImageThread()
    {
        // Check if communication address is available
        communicationAddress = netConfig.getCamAddress();
        bool AddressAvailable = !String.Equals(communicationAddress, "tcp://:");

        if (AddressAvailable)
        {
            handCommunicationAddress = netConfig.getCamAddress(1);
            receiveRunning = true;
            imageStreamer = new Thread(getRobotImage);
            imageStreamer.IsBackground = true;
            imageStreamer.Start();
            handImageStreamer = new Thread(getHandImage);
            handImageStreamer.IsBackground = true;
            handImageStreamer.Start();
            connectionEstablished = true;
        }
    }

    private void getRobotImage()
    {
        using (SubscriberSocket receiver = new SubscriberSocket())
        {
            receiver.Options.ReceiveHighWatermark = 1;
            receiver.Connect(communicationAddress);
            receiver.Subscribe("");
            while (receiveRunning)
            {
                byte[] imageBytes;
                if (receiver.TryReceiveFrameBytes(
                    TimeSpan.FromMilliseconds(100), out imageBytes))
                    Interlocked.Exchange(ref latestImage, imageBytes);
            }
        }
    }

    private void getHandImage()
    {
        using (SubscriberSocket receiver = new SubscriberSocket())
        {
            receiver.Options.ReceiveHighWatermark = 1;
            receiver.Connect(handCommunicationAddress);
            receiver.Subscribe("");
            while (receiveRunning)
            {
                byte[] imageBytes;
                if (receiver.TryReceiveFrameBytes(
                    TimeSpan.FromMilliseconds(100), out imageBytes))
                    Interlocked.Exchange(ref latestHandImage, imageBytes);
            }
        }
    }

    private void StopImageThreads()
    {
        receiveRunning = false;
        if (imageStreamer != null && imageStreamer.IsAlive)
            imageStreamer.Join(300);
        if (handImageStreamer != null && handImageStreamer.IsAlive)
            handImageStreamer.Join(300);
        imageStreamer = null;
        handImageStreamer = null;
        Interlocked.Exchange(ref latestImage, null);
        Interlocked.Exchange(ref latestHandImage, null);
        connectionEstablished = false;
    }

    private void CreateHandCameraOverlay()
    {
        GameObject existingOverlay = GameObject.Find("HandCameraOverlay");
        if (existingOverlay != null)
        {
            handImage = existingOverlay.GetComponent<RawImage>();
            return;
        }
        GameObject overlay = new GameObject(
            "HandCameraOverlay",
            typeof(RectTransform),
            typeof(CanvasRenderer),
            typeof(RawImage));
        overlay.transform.SetParent(image.transform.parent, false);
        RectTransform rect = overlay.GetComponent<RectTransform>();
        rect.anchorMin = new Vector2(0.5f, 0.5f);
        rect.anchorMax = new Vector2(0.5f, 0.5f);
        rect.pivot = new Vector2(0.5f, 0.5f);
        rect.sizeDelta = new Vector2(190f, 190f);
        rect.anchoredPosition = new Vector2(215f, 70f);
        handImage = overlay.GetComponent<RawImage>();
        handImage.raycastTarget = false;
        // Keep the camera's vertical correction and mirror it horizontally so
        // hand motion matches the operator's screen-space intuition.
        handImage.uvRect = new Rect(1f, 1f, -1f, -1f);
        overlay.transform.SetAsLastSibling();
    }

    public IEnumerator Start()
    {
        // Getting the Network Config Updater gameobject
        GameObject netConfGame = GameObject.Find("NetworkConfigsLoader");
        netConfig = netConfGame.GetComponent<NetworkManager>();
        while (netConfig != null && !netConfig.IsReady)
            yield return null;

        // Initializing the image texture
        texture = new Texture2D(256, 256, TextureFormat.RGB24, false);
        image.texture = texture;
        CreateHandCameraOverlay();
        handTexture = new Texture2D(128, 128, TextureFormat.RGB24, false);
        handImage.texture = handTexture;
    }

    public void Update()
    {
        if (connectionEstablished)
        {
            // To check if the same IP is being used
            if (String.Equals(communicationAddress, netConfig.getCamAddress()) &&
                String.Equals(handCommunicationAddress, netConfig.getCamAddress(1)))
            {
                // JPEG decode and texture upload run on Unity's main thread.
                // Cap them to the producer rate and atomically discard stale
                // frames so a backlog can never accumulate.
                if (Time.unscaledTime >= nextTextureUpdate)
                {
                    nextTextureUpdate = Time.unscaledTime + TextureUpdateInterval;
                    byte[] imageBytes = Interlocked.Exchange(ref latestImage, null);
                    if (imageBytes != null)
                        texture.LoadImage(imageBytes, false);
                    byte[] handImageBytes = Interlocked.Exchange(ref latestHandImage, null);
                    if (handImageBytes != null)
                        handTexture.LoadImage(handImageBytes, false);
                }
            }
            else
            {
                StopImageThreads();
            }
        } else
        {
            StartImageThread();
        }
    }

    private void OnDestroy()
    {
        StopImageThreads();
    }
}
