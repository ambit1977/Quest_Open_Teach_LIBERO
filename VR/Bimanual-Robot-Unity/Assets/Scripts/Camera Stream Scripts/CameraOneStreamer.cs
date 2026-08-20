using UnityEngine;
using UnityEngine.UI;

using NetMQ;
using NetMQ.Sockets;

using System;
using System.Collections.Generic;
using System.Threading;

public class CameraOneStreamer : MonoBehaviour
{
    private Thread imageStreamer;
    private Thread handImageStreamer;
    private List<byte[]> imageList;
    private List<byte[]> handImageList;
    private readonly object imageLock = new object();
    private readonly object handImageLock = new object();

    public RawImage image;
    private RawImage handImage;
    private Texture2D texture;
    private Texture2D handTexture;

    //public NetworkConfigs netConf;
    private bool connectionEstablished = false;
    private string communicationAddress;
    private string handCommunicationAddress;
    private NetworkManager netConfig;
    private SubscriberSocket socket;
    private SubscriberSocket handSocket;

    private void StartImageThread()
    {
        // Check if communication address is available
        communicationAddress = netConfig.getCamAddress();
        bool AddressAvailable = !String.Equals(communicationAddress, "tcp://:");

        if (AddressAvailable)
        {
            StartConnection();
            imageList = new List<byte[]>();
            handImageList = new List<byte[]>();
            imageStreamer = new Thread(getRobotImage);
            imageStreamer.IsBackground = true;
            imageStreamer.Start();
            handImageStreamer = new Thread(getHandImage);
            handImageStreamer.IsBackground = true;
            handImageStreamer.Start();
        }
    }

    public void StartConnection()
    {
        // Initiate Subscriber Socket
        socket = new SubscriberSocket();
        socket.Options.ReceiveHighWatermark = 1000;
        socket.Connect(communicationAddress);
        socket.Subscribe("");
        handCommunicationAddress = netConfig.getCamAddress(1);
        handSocket = new SubscriberSocket();
        handSocket.Options.ReceiveHighWatermark = 2;
        handSocket.Connect(handCommunicationAddress);
        handSocket.Subscribe("");
        connectionEstablished = true;
    }

    private void getRobotImage()
    {
        while (true)
        {
            byte[] imageBytes = socket.ReceiveFrameBytes();
            lock (imageLock)
            {
                imageList.Add(imageBytes);
                if (imageList.Count > 2)
                    imageList.RemoveAt(0);
            }
        }
    }

    private void getHandImage()
    {
        while (true)
        {
            byte[] imageBytes = handSocket.ReceiveFrameBytes();
            lock (handImageLock)
            {
                handImageList.Add(imageBytes);
                if (handImageList.Count > 2)
                    handImageList.RemoveAt(0);
            }
        }
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
            typeof(RawImage),
            typeof(Outline));
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
        Outline outline = overlay.GetComponent<Outline>();
        outline.effectColor = Color.white;
        outline.effectDistance = new Vector2(4f, -4f);
        overlay.transform.SetAsLastSibling();
    }

    public void Start()
    {
        // Getting the Network Config Updater gameobject
        GameObject netConfGame = GameObject.Find("NetworkConfigsLoader");
        netConfig = netConfGame.GetComponent<NetworkManager>();

        // Initializing the image texture
        texture = new Texture2D(640, 360, TextureFormat.RGB24, false);
        image.texture = texture;
        CreateHandCameraOverlay();
        handTexture = new Texture2D(256, 256, TextureFormat.RGB24, false);
        handImage.texture = handTexture;
    }

    public void Update()
    {
        if (connectionEstablished)
        {
            // To check if the same IP is being used
            if (String.Equals(communicationAddress, netConfig.getCamAddress()))
            {
                // Getting the image from the queue and displaying it
                lock (imageLock)
                {
                    if (imageList.Count > 0)
                    {
                        texture.LoadImage(imageList[imageList.Count - 1]);
                        imageList.Clear();
                    }
                }
                lock (handImageLock)
                {
                    if (handImageList.Count > 0)
                    {
                        handTexture.LoadImage(handImageList[handImageList.Count - 1]);
                        handImageList.Clear();
                    }
                }
            }
            else
            {
                // Aborting the queue
                imageStreamer.Abort();
                connectionEstablished = false;
            }
        } else
        {
            StartImageThread();
        }
    }
}
