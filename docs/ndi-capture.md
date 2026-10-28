# Private NDI® capture on your local network

Read subtitles from a game that runs on another device, such as an iPhone, an
iPad or a console connected to a streaming PC. The device sends its screen over
[NDI®](https://ndi.video) on your home network. The Windows companion on this
PC reads the frames with local OCR. Prepared tables, original voices, reading
tools and phone sharing then work as they do for a game window.

Video goes directly between your devices. The toolkit adds no relay, cloud
service or account. This differs from the [VDO.Ninja mobile mode](mobile-capture.md),
whose hosted viewer may use external relays but lets the PC stay off.

## Privacy

- NDI streams are not encrypted. Anyone on the same network can discover and
  watch them. Use NDI only on a network you trust, never on public Wi-Fi.
- Stop the broadcast on the sending device when you finish playing.
- Frames are processed in memory on this PC. Only matched transcript lines and
  calibration are saved, as with window capture.

## Set up

1. Install the free **NDI Runtime** on this PC. It is included in
   [NDI Tools](https://ndi.video/tools/). The toolkit does not ship it.
   The companion finds a new installation without a restart.
2. On the sending device, start an NDI screen broadcast. On iOS, use an NDI
   screen-capture app from the App Store. On a streaming PC, OBS can send NDI
   with an NDI plugin. Keep both devices on the same network.
3. In the companion, prepare the game's learning language in
   **Setup → Languages**, as for window capture. The game's files must be
   installed on this PC because tables and original voices come from them.
4. Open **Capture setup** for that game. Under **Capture source**, choose
   **NDI® video on my local network**, then choose the broadcast in
   **NDI source**. Use **Search again** if it is not listed yet.
5. Save, start capture, and use the live preview to calibrate the subtitle
   region against the received picture.

To return to the game window, choose **Game window on this PC** and save.

## Behavior and limits

- The capture region is relative to the received NDI picture, so calibrate it
  separately from the PC window. iOS limits screen broadcasts to 1920 pixels on
  the longer side; small subtitles may need a larger region.
- Capture reads the newest received frame when it scans and discards older
  queued frames without converting them.
- When a static scene stops a sender, the last frame is reused for up to five
  seconds. Capture then reports that it is waiting for video and recovers when
  frames return. A lost connection is reopened automatically.
- One NDI game is configured at a time. Choosing NDI for another game moves it.
- The receiver requests uncompressed BGRX frames; the NDI Runtime decodes
  NDI|HX streams itself.
- Automated checks use a synthetic NDI runtime. They verify the SDK structure
  layouts, frame conversion and capture integration, not a physical sender.

NDI® is a registered trademark of Vizrt NDI AB.
