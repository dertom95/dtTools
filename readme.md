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
- |enum:key,enum_name *captures input as enum value for the corresponding key. alle enums captures under this enum_name will be options for this input*/
  ```
   /*name:type|enum:int,ctype*/int/*endname*/ intValue=0;  
  ```
- |enum_mod
- |enum_strict
- |default : value that is used in the template
- |map
- |getmap
- |if:condition,true-output,false-output
  ```
  /*name:if|auto|if:@returnType!='void',@default,*/return/*endname*/  
  ```
- |
</code>


TODO: FIX If-Blocks
TODO: enum: dynamic add e.g. classname (runtime have to write in xsd!?)
TODO: names: global decorators that are valid for all names of this type. (e.g. replace '['=>'<' should be applied to all types so you won't need to add this command everywhere

