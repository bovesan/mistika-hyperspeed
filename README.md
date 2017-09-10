# mistika-hyperspeed
This project provides a framework for extending or tweaking a SGO Mistika or Mamba system, and also includes several such extensions. The screenshots might not show all current extensions.
They are divided into the following categories:
* [Tools](#tools)
* [Afterscripts](#afterscripts)
* [Stacks](#stacks)
* [Configs](#configs)
* [Web links](#web-links)
* [Modules](#modules)
  * [hyperspeed.mistika](#hyperspeedmistika)
  * [hyperspeed.stack](#hyperspeedstack)

To get started, run **./hyperspeed-dashboard.py**
## Tools
![Screenshot](http://bovesan.com/wp-content/uploads/2017/09/Screen-Shot-2017-09-10-at-20.02.54.png)
Scripts or programs which can be run manually or at specific intervals to perform any task. You can also show these in the Extras panel in Mistika.
Each tool must have its own folder under the Tools directory, and must include a **config.xml**:
### Tools config.xml structure
* tool
    * alias: The name of the tool
    * description: A description of the tool
    * executable: The name of the file to run

## Afterscripts
![Screenshot](http://bovesan.com/wp-content/uploads/2017/09/Screen-Shot-2017-09-10-at-20.04.04.png)
Scripts or programs which can be run automatically after a successful render, or launch manually on a previously rendered stack (typically an .rnd).
Each afterscript must have its own folder under the Afterscripts directory, and must include a **config.xml**:
### Afterscripts config.xml structure
* afterscript
    * alias: The name of the afterscript
    * description: A description of the afterscript
    * executable: The name of the file to run

## Stacks
![Screenshot](http://bovesan.com/wp-content/uploads/2017/09/Screen-Shot-2017-09-10-at-20.04.11.png)
Effect presets made from standard Mistika effects and/or custom footage, fonts, LUTs or even GLSL shaders.
If the stack has *dependencies*, these must be included in the same folder. hyperspeed-dashboard.py will let you *install* a stack by relinking any dependencies.
## Configs
![Screenshot](http://bovesan.com/wp-content/uploads/2017/09/Screen-Shot-2017-09-10-at-20.04.18.png)
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
## Modules
The modules found in the *hyperspeed* subfolder are the backbone of the project. These provide classes and functions for Mistika related work. Think of them as an **unofficial** API. Here is a brief overview. For a complete list, please look at the source code.
### hyperspeed.mistika
##### mistika.env_folder
##### mistika.tools_path
##### mistika.shared_folder
##### mistika.version
##### mistika.project
##### mistika.user
##### mistika.settings
A dictionary of all the settings in *.mistikarc*
##### mistika.product
*Mistika* or *Mamba*
##### mistika.projects_folder
##### mistika.afterscripts_path
##### mistika.fonts_config_path
##### mistika.scripts_folder
##### mistika.glsl_folder
##### mistika.lut_folder
##### mistika.fonts
##### mistika.fonts_folder
### hyperspeed.stack
##### stack.Stack(path)
Loads a Mistika structure (env, grp, fx etc.) and creates a `Stack` object.
###### Stack.size
Returnes the size (in bytes) of the file.
###### Stack.project
If file is a render, this holds the project as `string`. Else `None`.
###### Stack.resX
If file is a render, this holds the horizontal resolution as `int`. Else `None`.
###### Stack.resY
If file is a render, this holds the horizontal resolution as `int`. Else `None`.
###### Stack.fps
If file is a render, this holds the JobFrameRate as `string`. Else `None`.
###### Stack.frames
If file is a render, this holds the render duration (in frames) as `int`. Else `None`.
###### Stack.groupname
This property returns the name of the first (top level) group in the stack. Does not work if there are multiple groups on the same level.
###### Stack.tags
A list of any tags, specified by `#` in the `Stack.groupname`.
###### Stack.title
The `Stack.groupname` with any tags stripped away, or the name of the file, if no groupname was found.
###### Stack.comment
This property returns the first (top level) comment attribute in a stack.
###### Stack.dependencies
Returns a full list of file dependencies for a stack, as `Dependency` objects.
###### Stack.iter_dependencies(self, progress_callback=False, relink=False)
Get the dependency, one at the time. *progress_callback* let's you monitor the progress monitor the progress from a custom function `progress_callback(float)`
###### Stack.relink_dependencies()
This function goes through all missing dependencies and looks for a match in the folder of the stack (and subfolders). Will overwrite the stack, but hides the original (a . is prepended to the file name). Fonts cannot be relinked, but the module will try to copy fonts file to the systems font folder, `hyperspeed.mistika.fonts_folder`
##### stack.Dependency(name, f_type, start=False, end=False, parent=None))
###### Dependency.type
One of the following types:
* dat
* glsl
* lut
* highres
* lowres
* audio
* lnk
* font
###### Dependency.name
Identifier of the dependency. Depending on `Dependency.type`, this may or may not be a full path.
###### Dependency.path
The full path of the file.
###### Dependency.frame_ranges
A list of `DependencyFrameRange` objects for the current dependency. If a media item is used multiple times in a stack, this lists all the different frame ranges in use.
###### Dependency.size
Returns the size of the file. If the item is an image sequence, returns the combined size of all the frames in use. If file does not exist, returns `None`.
###### Dependency.complete
Returns `True` if the file(s) exists. If not, `False`.
