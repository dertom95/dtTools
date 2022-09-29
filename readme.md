dtTools

Block-Decorators:
- |ifset:ifID,var,value *checks if var==value ifID needs to be set if multiple ifs or else is used*
  ```
  /*block:params|ifset:0,type,string*/
  /*block:params|else:0*/
  ```
- |else:ifID *checks if this ifID is not triggered,yet. sample see ifset*
- |file:%s.h,name : write filename python string with replacements after first comma
- |overwrite : overwrites file? todo: isn't that default?
- |output : output in alternative block (same level)
  ```
  /*block:loop|output:codeflow*/
          ...
  /*endblock:loop*/d

  /*block:codeflow*//*endblock:codeflow*/
  ```
- |reference:ref-name : adds reference to this block to be reuse via /*block-ref:ref-name*/../*endblock-ref*/

<code>Name-Decorators:
- |required : attribute is required
- |auto : *element is triggered even without input*
- |fu : *input first character upper-case* e.g. 
- |l  : convert string to lower characters
- |u  : convert string to uppper characters
- |replace,from,to : replaces 'from' string with 'to'-string
- |c2s : convert CamelCase to snake_case
- |pre:prefix : *prefix to input*
- |post:postfix : *postfix to input*
- |post_n_blast:postfix,[tag-filter] : *postfix if not last block*, use tag-filter to only count idx and len of specified tag-type. use 'comma' as keyword if needed (dont use the character itself in combination with filter)
  ```
  post_n_blast:comma,field
  ```
- |store
- |lstore
- |lget
- |echo:string,var1,var2,... : *corresponds to python str % (var1,var2,...). 
  special vars: 
    * @=input 
    * @default=(value of template @scoped_value_name) 
    * @idx=(elem-idx in xml-block) 
    * @idx#tag=(elem-idx of this tag in the current xml-block)
  ```
  /*name:name|echo:%s_%s,@class.name,@*/Audio_SetMode/*endname*/
  ```
- |enum:key,enum_name *captures input as enum value for the corresponding key. all enums captured under this enum_name will be options for this input*/
  ```
   /*name:type|enum:int,ctype*/int/*endname*/ intValue=0;  
  ```
- |enum_add : add a name to a specific enum
  * enum_add:ctype
- |enum_mod : modifies an enum-output for a specific enum-item: 
  * enum_mod:type,float,%sf    <--append f
  * enum_mod:type,string,"%s"  <--wrap in dquotes
- |enum_strict : only available enum-values are possible, not freetext
- |default : value that is used in the template
- |map
- |getmap
- |if:condition,true-output,false-output
  ```
  /*name:if|auto|if:@returnType!='void',@current,*/return/*endname*/  
  true and false-outputs can use variables via @-notation.
  @current=the enclosed value
  or @varname e.g. Key[@keyid]
  ```
 
</code>

Names can reuse 'names' from another scope. e.g. from the parent block. You only need to identify the reused 'name' with its parent's blockname:  
e.g. outer.dataName (If outer itself would be a nested block, you won't need to go the whole route from the root element, just the one blockname)  

Let's say we have following(sry, markdown cannot show the right notation):  
<code>
/*block:outer*/  
// /*name:dataName*/All this will be replaced by 'name'/*endname*/  
  
/*block:inner*/  
// reuse outer 'dataName' from within new block: /*name:outer.dataName*/  dataName-Value from outer.dataName comes here/*endname*/  
/*endblock:inner:*/  
/*endblock:outer*/  
</code>

example-config:
```
{
    "name" : "service-generator",
    "rootname": "root",
    "config" : {
        "xsd-schema-name":"dtEndzone",
        "xsd-output":"${configfolder}/gen/xsd/dtEndzone.xsd",
        "gen-input-file":["${configfolder}/input/services/sample.xml"],
        "gen-input-folder":["${configfolder}/input/services"],
        "gen-root-folder":"${configfolder}/../Services",
		"gen-inputfile-if-missing":true,
        "start-runtime":true
    },
    "templates": [
        {
            "name": "interface",
            "path": "${configfolder}/templates/GeneratorServiceInterface.cs",
            "onlyParse" : true
        },
        {
            "name": "service_impl",
            "path": "${configfolder}/templates/GeneratorServiceImpl.cs"
        }
    ],
	"imports" : [
		"gen_clazz.json"
	]
}
```


TODO: more dynamic decorators for names and blocks
TODO: FIX If-Blocks
TODO: make blocks cross template referenceable to prevent tedious work of the same stuff. e.g. parameter-block give it an it, and in block create decorator like: /*block:param|ref:service.method.param*/.../*endblock:*/
TODO: kick rip-blocks from autocompletion (/*block:rip*/) (but it still needs to be processed, because you might have enum-declarations in it)
TODO: post_n_blast should be really a block-decorator
~~TODO: enum: dynamic add e.g. classname (runtime have to write in xsd!?)~~
TODO: names: global decorators that are valid for all names of this type. (e.g. replace '['=>'<' should be applied to all types so you won't need to add this command everywhere

