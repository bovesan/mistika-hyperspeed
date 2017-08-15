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
Each tool must have its own folder under the Tools directory, and must include a **config.xml** similar to this:
```xml
<?xml version="1.0"?>
<tool>
    <alias>Consolidate</alias>
    <description>Copies a stack (.env, .grp etc.) including all dependencies (media, glsl, LUTs etc.) to a given location.</description>
    <executable>consolidate.py</executable>
</tool>
```
## Afterscripts
Scripts or programs which can be run automatically after a successful render, or launch manually on a previously rendered stack (typically an .rnd).
Each afterscript must have its own folder under the Afterscripts directory, and must include a **config.xml** similar to this:
```xml
<?xml version="1.0"?>
<config>
    <alias>Benchmark</alias>
    <description>Measures render performance by the difference in modification time of the .rnd file and the rendered video file. Will only work correctly on single segments.</description>
    <executable>Benchmark.py</executable>
</config>
```
## Stacks
Effect presets made from standard Mistika effects and/or custom footage, fonts, LUTs or even GLSL shaders.
If the stack has *dependencies*, these must be included in the same folder. hyperspeed-dashboard.py will let you *install* a stack by linking any dependencies.
> [Installation is not yet implemented](https://github.com/bovesan/mistika-hyperspeed/issues/5)
## Configs
Various tweaks that can be enabled or disabled from the dashboard.
Each config must have its own folder under the Configs directory, and must include a **config.xml** similar to this:
```xml
<?xml version="1.0"?>
<config>
    <alias>Flopped 2 monitor layout</alias>
    <description>Puts the timeline on the right and the composer on the left.</description>
    <links>
    	<link>
    		<target>2_LAYOUT.sup</target>
    		<location>$MISTIKA-ENV$/config/2_LAYOUT.sup</location>
    	</link>
    </links>
    <manage>false</manage>
</config>
```
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
