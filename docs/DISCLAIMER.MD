# Release Notes – O11Pro Unpacked Version

Thank you to everyone who has shown interest in this project. To avoid any misunderstandings, please take a moment to read the following notes regarding this release.

---

## What is the "Unpacked Version"?

This release is an **unpacked version of the O11Pro cracked/nulled build**. The version that was originally distributed was protected using a packer (UPX), and this release removes that layer to make the executable easier to analyze.

Please understand that:

* This is an unpacked executable.
* The internal structure is easier to study and patch.
* Embedded resources from the binary are included for analysis purposes.
* This is **not** the original O11Pro source code.
* I do **not** have access to the official source code.
* This release was **not** rebuilt from source.

---

## Patches and Improvements

Since the original source code is unavailable, any fixes or modifications have been performed directly at the binary level through reverse engineering techniques, including:

* Assembly analysis.
* Patching specific functions.
* Adjusting execution flow to improve stability and ensure features operate correctly.
* Monitoring future releases for changes and compatibility.

Some portions of the executable may still retain structures inherited from the original packed build.

---

## Important Notes

* This release is intended for research, analysis, and reverse engineering study purposes.
* It should not be considered an official release from the original developers.
* An unpacked executable does **not** mean clean or recovered source code.
* If you encounter any issues or bugs, please provide sufficient information to reproduce them when reporting.
* To make everything work properly, we must defeat the obfuscated JavaScript file first: [index-BX-yLeHZ.js](../resources/static/index-BX-yLeHZ.js)

---

## Contributions

Experienced reverse engineers are welcome to contribute by:

* Reviewing and improving existing patches.
* Suggesting enhancements and optimizations.
* Submitting pull requests and sharing improvements with the community.

Community contributions are appreciated and help improve the quality of the project over time.

---

## Final Notes

This release exists out of curiosity and interest in reverse engineering. It is not intended to claim ownership of the original software, but rather to document and study how a packed executable can be restored to a more analyzable state.

**Unpacked does not mean original source code. It simply means that the packing layer has been removed, making the binary easier to study, debug, and patch.**

---

## Disclaimer

This release relates only to the unpacking and analysis of the executable obtained by the maintainer. All copyrights, trademarks, and intellectual property rights associated with O11Pro remain the property of their respective owners.
