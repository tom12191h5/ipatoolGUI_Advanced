# ipatoolsGUI_Advanced
This is a GUI tool based on ipatool, built using Python and PyQt5. Theoretically, you can run this program on any platform.

## Prepare
1.open console and run 
```
$ brew install ipatool
```
2.login
```
ipatool auth login -e your_apple_id@email.com -p YourPassword
```
More details see on:https://github.com/majd/ipatool


## Introduce
The program has three parts: the first part is the search area, the second part is the version list, and the third part is the download area.

## How to use
Enter the name of the application you want to search in the search area and click search. Then click on the target application. The version ID will be automatically filled into the input box in the second part; you don't need to do it manually. Then click search in the second part, and you will get detailed information on 10 historical versions. You can enter the number of historical versions you want to retrieve in the input box next to it. After clicking on the corresponding version, click the download button, and the downloaded IPA will be placed in the location you specify.

## Preview
This is the program's preview interface.
<img width="996" height="926" alt="截屏2026-04-21 00 49 04" src="https://github.com/user-attachments/assets/dfb3d473-93ab-42e2-b384-48db356c9d50" />

## Security Update
## 🔒 Security Enhancements Overview

This update introduces multiple layers of security hardening across input validation, command execution, file handling, and data parsing. Below is a summary of the key improvements:

---

### 🧼 Input Validation & Sanitization

* **Strict Bundle ID validation**

  * Enforces reverse-domain format
  * Limits length (≤255 chars)
  * Prevents malformed or malicious identifiers

* **Keyword filtering**

  * Restricts length (≤100 chars)
  * Allows only safe characters (alphanumeric, spaces, basic symbols, CJK)

* **Filename safety checks**

  * Blocks dangerous characters (`\/:*?"<>|`)
  * Enforces reasonable length limits

* **ANSI escape removal**

  * Cleans terminal output to prevent injection or parsing issues

---

### ⚙️ Secure Command Execution

* **No `shell=True` usage**

  * All subprocess calls use argument lists to prevent command injection

* **Timeout protection**

  * Prevents hanging processes

* **Controlled error handling**

  * Gracefully handles missing binaries, timeouts, and unexpected failures

---

### 📦 Safe JSON Extraction

* **Regex + size-limited parsing**

  * Prevents ReDoS (Regular Expression Denial of Service)
  * Caps maximum input size

* **Robust error handling**

  * Avoids crashes from malformed JSON

---

### 📁 File System Protection

* **Path validation**

  * Resolves and validates output paths safely
  * Blocks:

    * Path traversal (`..`)
    * Symbolic links

* **Optional directory restriction**

  * Can limit downloads to trusted locations (e.g., user home directory)

---

### 🧵 Threading & Execution Safety

* **Thread pool limits**

  * Caps concurrent tasks to prevent resource exhaustion

* **Safe thread lifecycle management**

  * Tracks and cleans up worker threads properly

---

### 📊 UI & Interaction Safeguards

* **Input length limits in UI fields**

* **Disable UI during execution**

  * Prevents race conditions and duplicate actions

* **Progress parsing with validation**

  * Extracts percentage safely from output

---

### ⚠️ Error Containment

* All critical operations wrapped in `try/except`
* User-facing errors are sanitized and truncated
* Prevents leakage of sensitive system details

---

### ✅ Summary

This version significantly improves security by:

* Eliminating command injection risks
* Hardening user input validation
* Securing file system interactions
* Preventing parsing and resource abuse attacks
* Improving overall robustness and fault tolerance

---

### 🔐 Usage Reminder

* Ensure authentication is done via `ipatool auth`
* Use only in trusted environments
* Follow applicable legal and platform guidelines when downloading apps

---
