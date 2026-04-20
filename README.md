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
