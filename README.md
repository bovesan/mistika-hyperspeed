# mistika-hyperspeed
This project provides a framework for extending or tweaking a SGO Mistika or Mamba system, and also includes several such extensions.
They are divided into the following categories:
* [Tools](#tools)
* [Afterscripts](#afterscripts)
* [Stacks](#stacks)
* [Configs](#configs)
* [Web links](#web-links)

To get started, run **./hyperspeed-dashboard.py**
## Tools
Scripts or programs which can be run manually or at specific intervals to perform any task. You can also show these in the Extras panel in Mistika.
Each tool must have its own folder under the Tools directory, and must include a **config.xml**:
### Tools config.xml structure
* tool
    * alias: The name of the tool
    * description: A description of the tool
    * executable: The name of the file to run

## Afterscripts
Scripts or programs which can be run automatically after a successful render, or launch manually on a previously rendered stack (typically an .rnd).
Each afterscript must have its own folder under the Afterscripts directory, and must include a **config.xml**:
### Afterscripts config.xml structure
* afterscript
    * alias: The name of the afterscript
    * description: A description of the afterscript
    * executable: The name of the file to run

## Stacks
Effect presets made from standard Mistika effects and/or custom footage, fonts, LUTs or even GLSL shaders.
If the stack has *dependencies*, these must be included in the same folder. hyperspeed-dashboard.py will let you *install* a stack by linking any dependencies.
> [Installation is not yet implemented](https://github.com/bovesan/mistika-hyperspeed/issues/5)
## Configs
Various tweaks that can be enabled or disabled from the dashboard.
Each config must have its own folder under the Configs directory, and must include a **config.xml**:
### Configs config.xml structure
* config
    * alias: The name of the afterscript
    * description: A description of the afterscript
    * links: One or more files to install on the system
        * link ```setting the attribute copy="yes" will copy the file instead of linking```
            * target: The file to be linked/copied
            * location: The destination on the system
    * manage: Set to true if you need to run a custom script to install, detect or remove the tweak. This must be an excecutable named *manage*, accepting the following arguments:
        * manage install
        * manage remove
        * manage detect

## Web links
Various Mistika related links.
Stored as xml in the following format:
```xml
<?xml version="1.0"?>
<link>
  <alias>sgo.es</alias>
	<link>
		<alias>Support home</alias>
		<url>http://support.sgo.es/support/home</url>
	</link>
</link>
```
