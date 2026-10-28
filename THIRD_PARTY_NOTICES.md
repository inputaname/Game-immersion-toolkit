# Third-party notices

The Firebird55 license covers original project code only. Dependencies retain their own terms: React/React DOM (Meta, MIT), Base UI (MUI, MIT), Lucide (ISC), TypeScript (Microsoft, Apache-2.0). Package metadata and dependency distributions contain their upstream notices. Builds and consumers must retain notices for dependencies they bundle.

The component uses documented Lexirise interfaces; this repository does not redistribute Lexirise's website bundles, account data or dictionaries. Public upstream bundles inspected by the compatibility watcher remain ignored local review material.

## Toolkit assets and tools

- FireRedVAD ONNX model and CMVN data: FireRedTeam, Apache-2.0. Full license, source revision and file hashes are in assets/fireredvad. These terms remain independent of the project license.
- Original PT launcher icon and favicon: generated from project-owned geometric shapes. Covered by LICENSE.
- shadcn-derived styling: retain styles/SHADCN-LICENSE.md (MIT).
- Geist and Geist Mono fonts: Copyright 2024 The Geist Project Authors, SIL Open Font License 1.1. Both families use the identical full notice in styles/GEIST-OFL.txt, also included in release THIRD_PARTY_LICENSES.txt. The notices were verified against google/fonts revision bd8f81ddb5c74d5c8897b36ad88b440266245103 (ofl/geist/OFL.txt and ofl/geistmono/OFL.txt). The font license remains independent of the project license.
- oneocr's Python wrapper is MIT. Windows Snipping Tool's proprietary OCR DLL/model files are read from the user's installed software during setup; they are not redistributed here.
- windows-capture (MIT) supplies Windows Graphics Capture for unfocused games. Its opencv-python dependency uses Apache-2.0 and includes upstream notices in its installed distribution. Both are installed from the locked Python manifest.
- FFmpeg downloaded through imageio-ffmpeg, FModelCLI (GPL-3.0), WolvenKit and game-extraction dependencies remain separate installed/downloaded tools with their own license notices. They are not included in toolkit source or installer ZIPs; retain their notices when using or distributing them independently.
- scripts/extract_voice_links.mjs loads a separately downloaded GalScript reader from simon300000/zenless-voice (MIT, copyright 2024 simon3000). Setup retains its full license beside the pinned reader in the ignored local tool cache. Its ooz-wasm (GPL-3.0-or-later) and xxhash-wasm (MIT) dependencies retain their own notices. Neither game metadata nor the reader is bundled as original project code.
- vgmstream is downloaded from its official r2117 Windows x64 release with full COPYING and dependency notices retained. The REE unpacker is downloaded separately from Ekey/REE.PAK.Tool; its upstream terms apply, and the project license grants no redistribution rights over that tool. Tool downloads are checksum verified and excluded from source/installer bundles.
- Optional NDI® capture loads the NDI Runtime that the user installs from [ndi.video](https://ndi.video/tools/) and calls its C API with ctypes. The NDI SDK, runtime and headers are not redistributed; structure layouts follow the SDK's MIT-licensed headers. NDI® is a registered trademark of Vizrt NDI AB, and the runtime remains under its own license.
- Game scripts, subtitle catalogs, audio, recordings and extracted archives belong to their respective publishers and remain user-local. The project license grants no rights over game content.
- Mobile OCR: pinned Tesseract.js/Tesseract.js-core 7.0.0 (Apache-2.0) and naptha/tessdata English, Simplified Chinese and Traditional Chinese models (Apache-2.0), obtained through pinned @tesseract.js-data packages. The generated Pages allowlist includes the runtime's distribution notices, Apache license, model provenance and checksums. Model weights retain the upstream license independently of the npm wrapper's MIT metadata. Authored browser test captions and generated tone/video fixtures contain no game content and are covered by LICENSE.
- Chinese capture matching: opencc-python-reimplemented 0.1.7 (Apache-2.0) and OpenCC-JS 1.4.2 (MIT implementation, Apache-2.0 dictionary derivatives). Conversion runs locally on lookup keys; official transcript text is preserved. The browser distribution includes OpenCC-JS and dictionary notices and licenses.
- Mobile QR pairing: qrcode-generator 2.0.4 (Kazuhiko Arase, MIT), jsQR 1.4.0 (Apache-2.0), and fflate 0.8.3 (MIT). Pinned runtime assets and complete notices are self-hosted in the Pages allowlist. Camera frames and pairing messages are processed on the devices.
- NTE uses a separately downloaded UEExtractor v1.0.8.7 (SolicenTEAM, MIT; copyright 2024 Denis Solicen/Ambi) with its full notice saved beside the verified tool. Its CUE4Parse and decompression dependencies retain their own upstream terms. The toolkit-owned C# bridge calls that tool; no upstream binaries or source are bundled as project-owned code. Honkai's reviewed public 4.7 catalog is downloaded only into a private runtime cache from nairieberry/HonkaiImpactData; it is game-derived content and is not included in source or installers.

JavaScript and Python dependencies retain their distribution licenses. The locked manifests identify exact dependencies; installed packages carry their upstream notices. Do not describe all repository or runtime content as covered by the Firebird55 license.

Toolkit release bundles include THIRD_PARTY_LICENSES.txt with the complete license/notice files from the locked JavaScript dependency installation used for the build. This includes libraries bundled into the prebuilt frontend.


Endfield game tools download pinned MIT-licensed reader sources from
[EIHRTeam/EndfieldStudio](https://github.com/EIHRTeam/EndfieldStudio). Their license
notice remains beside the locally built reader. Sources, native binaries,
archive metadata and game data stay in ignored local tool storage and are not
bundled in the repository, release ZIP or public mobile preview.

## Additional native game readers

The Fox readers retain the complete Atvaark, Google CityHash and kapuragu MIT
notices in `backend/fox_dialogue.py`. The Decima container reader uses format
research from Jayveer/Decima-Explorer and ShadelessFox/decima-workshop; its
MurmurHash3 arithmetic follows the public-domain algorithm. The Decima-Explorer
notice is retained below. Original game-owned decompression libraries are loaded
from the user's installation and are not redistributed.

Persona character mapping tables are downloaded separately from the pinned
Atlus Script Tools revision documented in the game audit. Their GPL-3.0 license
and source notice remain beside those tables in the private cache. Neither the
tables nor upstream executable code are bundled in the toolkit distribution.

The independently implemented Deus Ex readers reference the BIGFILE/CDRM/DRM
format research in Gibbed.CrystalDynamics and rrika/dxhr. They are not upstream
Gibbed tools. The Gibbed format-reference notice is retained below. Other game
container readers are described with their format references in the respective
source modules and game audits; these references confer no rights to game assets.

### Decima-Explorer — MIT License

Copyright (c) 2019 Jayveer Kathwadia

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

### Gibbed.CrystalDynamics — zlib License

Copyright (c) 2020 Rick (rick 'at' gibbed 'dot' us)

This software is provided 'as-is', without any express or implied
warranty. In no event will the authors be held liable for any damages
arising from the use of this software.

Permission is granted to anyone to use this software for any purpose,
including commercial applications, and to alter it and redistribute it
freely, subject to the following restrictions:

1. The origin of this software must not be misrepresented; you must not
   claim that you wrote the original software. If you use this software
   in a product, an acknowledgment in the product documentation would
   be appreciated but is not required.

2. Altered source versions must be plainly marked as such, and must not
   be misrepresented as being the original software.

3. This notice may not be removed or altered from any source
   distribution.
