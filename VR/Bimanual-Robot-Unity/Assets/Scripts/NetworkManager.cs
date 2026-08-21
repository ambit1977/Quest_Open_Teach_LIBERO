using System;
using System.Collections;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;
using TMPro;

[System.Serializable]
public class NetworkConfiguration
{
    public string IPAddress;
    public string rightkeyptPortNum;

    public string leftkeyptPortNum;
    public string camPortNum;
    public string graphPortNum;
    public string resolutionPortNum;

    public string PausePortNum;

    public string rightgripperPortNum;

    public string leftgripperPortNum;

    public string LeftPausePortNum;

    public string RightPausePortNum;

    public string LeftGripperRotatePortNum;

    public string RightGripperRotatePortNum;

    public bool isIPAllocated ()
    {
        if (String.Equals(IPAddress, "undefined"))
            return false;
        else
            return true;
    }
}

[DefaultExecutionOrder(-1000)]
public class NetworkManager : MonoBehaviour
{
    private const int DiscoveryPort = 8125;

    // Loading the Network Configurations
    public NetworkConfiguration netConfig;
    public bool IsReady { get; private set; }

    // Display variables for menu
    public TextMeshPro IPDisplay;

    // To indicate no IP
    private bool IPNotFound;

    public string getRightKeypointAddress()
    {
        if (IPNotFound)
            return "tcp://:";
        else
            return "tcp://" + netConfig.IPAddress + ":" + netConfig.rightkeyptPortNum;
    }

    public string getLeftKeypointAddress()
    {
        if (IPNotFound)
            return "tcp://:";
        else
            return "tcp://" + netConfig.IPAddress + ":" + netConfig.leftkeyptPortNum;
    }
    public string getCamAddress()
    {
        if (IPNotFound)
            return "tcp://:";
        else
            return "tcp://" + netConfig.IPAddress + ":" + netConfig.camPortNum;
    }

    public string getCamAddress(int portOffset)
    {
        if (IPNotFound)
            return "tcp://:";
        int port;
        if (!Int32.TryParse(netConfig.camPortNum, out port))
            return "tcp://:";
        return "tcp://" + netConfig.IPAddress + ":" + (port + portOffset);
    }

    public string getGraphAddress()
    {
        if (IPNotFound)
            return "tcp://:";
        else
            return "tcp://" + netConfig.IPAddress + ":" + netConfig.graphPortNum;
    }

    public string getResolutionAddress()
    {
        if (IPNotFound)
            return "tcp://:";
        else
            return "tcp://" + netConfig.IPAddress + ":" + netConfig.resolutionPortNum;

    }

    public string getPauseAddress()
    {
        if (IPNotFound)
            return "tcp://:";
        else
            return "tcp://" + netConfig.IPAddress + ":" + netConfig.PausePortNum;
        
    }

    public string getRightGripperAddress()
    {
         if (IPNotFound)
            return "tcp://:";
        else
            return "tcp://" + netConfig.IPAddress + ":" + netConfig.rightgripperPortNum;
    
    }

    public string getLeftGripperAddress()
    {
         if (IPNotFound)
            return "tcp://:";
        else
            return "tcp://" + netConfig.IPAddress + ":" + netConfig.leftgripperPortNum;
    
    }

    public string getLeftPauseStatus()
    {
        if (IPNotFound)
            return "tcp://:";
        else
            return "tcp://" + netConfig.IPAddress + ":" + netConfig.LeftPausePortNum;
    }

    public string getRightPauseStatus()
    {
        if (IPNotFound)
            return "tcp://:";
        else
            return "tcp://" + netConfig.IPAddress + ":" + netConfig.RightPausePortNum;
    }

     public string getLeftGripperRotateStatus()
    {
        if (IPNotFound)
            return "tcp://:";
        else
            return "tcp://" + netConfig.IPAddress + ":" + netConfig.LeftGripperRotatePortNum;
    }

    public string getRightGripperRotateStatus()
    {
        if (IPNotFound)
            return "tcp://:";
        else
            return "tcp://" + netConfig.IPAddress + ":" + netConfig.RightGripperRotatePortNum;
    }

    public void changeIPAddress(string IPAddress)
    {
        netConfig.IPAddress = IPAddress;
        IPNotFound = false;

        // Storing in the Oculus Player Preferences Dict
        PlayerPrefs.SetString("ipAddress", IPAddress);
        // Persist immediately. Quest apps may be force-stopped or suspended
        // without receiving Unity's normal application-quit callback.
        PlayerPrefs.Save();
    }

   


    void Awake()
    {
        var jsonFile = Resources.Load<TextAsset>("Configurations/Network");
        netConfig = JsonUtility.FromJson<NetworkConfiguration>(jsonFile.text);

        if (PlayerPrefs.HasKey("ipAddress"))
            netConfig.IPAddress = PlayerPrefs.GetString("ipAddress");

        if (!netConfig.isIPAllocated())
            IPNotFound = true;
        else
            IPNotFound = false;        
    }

    IEnumerator Start()
    {
        string discoveredAddress = null;
        string discoveryError = null;
        bool discoveryFinished = false;
        string configuredAddress = netConfig != null ? netConfig.IPAddress : "";
        string requestId = Guid.NewGuid().ToString("N");

        Thread discoveryThread = new Thread(() =>
        {
            UdpClient client = null;
            try
            {
                client = new UdpClient(0);
                client.EnableBroadcast = true;
                client.Client.ReceiveTimeout = 1400;
                string payload = "{\"id\":\"" + requestId
                    + "\",\"command\":\"discover\",\"stage\":3}";
                byte[] data = Encoding.UTF8.GetBytes(payload);

                client.Send(data, data.Length, new IPEndPoint(IPAddress.Broadcast, DiscoveryPort));
                if (!String.IsNullOrWhiteSpace(configuredAddress) &&
                    IPAddress.TryParse(configuredAddress, out IPAddress configuredIP))
                    client.Send(data, data.Length, new IPEndPoint(configuredIP, DiscoveryPort));

                IPEndPoint remote = new IPEndPoint(IPAddress.Any, 0);
                byte[] response = client.Receive(ref remote);
                string responseText = Encoding.UTF8.GetString(response);
                if (responseText.Contains("\"status\":\"discovered\"") &&
                    responseText.Contains("\"id\":\"" + requestId + "\""))
                    discoveredAddress = remote.Address.ToString();
            }
            catch (SocketException)
            {
                // No launcher response: retain the saved or packaged fallback.
            }
            catch (Exception exception)
            {
                discoveryError = exception.Message;
            }
            finally
            {
                client?.Close();
                discoveryFinished = true;
            }
        });
        discoveryThread.IsBackground = true;
        discoveryThread.Start();

        float deadline = Time.realtimeSinceStartup + 1.8f;
        while (!discoveryFinished && Time.realtimeSinceStartup < deadline)
            yield return null;

        if (!String.IsNullOrWhiteSpace(discoveredAddress))
        {
            changeIPAddress(discoveredAddress);
            Debug.Log("QUEST_DISCOVERY_FOUND " + discoveredAddress);
        }
        else
        {
            Debug.Log("QUEST_DISCOVERY_FALLBACK " + configuredAddress);
        }
        if (!String.IsNullOrEmpty(discoveryError))
            Debug.LogWarning("QUEST_DISCOVERY_ERROR " + discoveryError);
        IsReady = true;
    }

    void Update()
    {
        // Displaying IP information
        if (!IPNotFound)
            IPDisplay.text = "IP Address: " + netConfig.IPAddress;
        else
            IPDisplay.text = "IP Address: Not Specified";
    }
}
