#!/usr/bin/python3

import io
import json,os,sys,re
from pydoc import resolve
from time import sleep
import xml.etree.ElementTree as ET
from xml.dom import minidom
from watchdog.events import PatternMatchingEventHandler
from watchdog.observers import Observer

generation_root=None
option_force_overwrite=False
 
marker_pattern="\|<#.*?#>\|"

def convert_to_valid_xml(text,replace_brackets=False):
    # TODO: this pattern seems to be not suitable, as it will capture "..." inside text-fields. but for now...

    pattern = r'["][\w\s\<\>*[\<\>]+[\w\s]*["]'
    matches=re.findall(pattern,text)
    for match in matches:
        match_before = match
        match = match.replace("<","&lt;")
        match = match.replace(">","&gt;")

        text = text.replace(match_before,match)

    return text

def get_scope_and_name(name_data):
    name_name=None
    name_scope=None
    name_decos=None

    first = name_data.find('|') 
    if first!=-1:
        name_decos=name_data[first:]
        name_data=name_data[:first]

    last_dot_pos = name_data.rfind('.')
    if last_dot_pos==-1:
        name_name=name_data
    else:
        name_name=name_data[last_dot_pos+1:]
        name_scope=name_data[:last_dot_pos]  
    return name_scope,name_name,name_decos 

def strip_tag(tag):
    ns_char = tag.rfind('}')
    if ns_char==-1:
        return tag
    
    return tag[ns_char+1:]

class C:
    current_block_counter = 1000
    CONFIG_TEMPLATES    ="templates"
    CONFIG_COMMENT_START="comment_start"
    CONFIG_COMMENT_END  = "comment_end"
    CONFIG_ROOT_NAME  = "rootname"
    config_file_path = None
    config_folder = None
    config = None
    delimiter_start = None
    delimiter_end = None
    rootname = None

    def create_id():
        C.current_block_counter+=1
        return C.current_block_counter

class TTName:
    def __init__(self,data,default_value,ctx,scope=None):
        self.data = data
        self.default_value=default_value
        self.name_id = C.create_id()
        self.decorators=[]
        self.ctx=ctx
        self.scope=scope
        self.enum_type=None
        self.required=False

        name_info = data.split('|')
        self.name = name_info[0]

        self.decorators=name_info[1:]

        # fake apply for global decorators (enum)
        self.apply_decorators("init")
        # todo: decorators
    def has_decorator(self,deco_id):
        return deco_id in self.decorators        

    def get_marker(self):
        return "|<#%s#>|" % self.name_id

    def has_scope(self):
        return self.scope is not None

    def get_enum_type(self):
        return self.enum_type

    def replace_special_characters(self,st):
        return st.replace("&colon;",":")

    def apply_decorators(self,name):
        runtime_mode = self.ctx.runtime_mode
        store_name = None
        store_list_name = None

        for decorator in self.decorators:
            splits = decorator.split(':',1)
            deco_id = splits[0].lower()
            if len(splits)>1:
                splits[1]=self.replace_special_characters(splits[1])

            if deco_id == "auto":
                # is handled somewhere else
                continue
            if deco_id == "fu":
                if not runtime_mode:
                    continue
                name = name[0].upper() + name[1:]
            elif deco_id == "u":
                if not runtime_mode:
                    continue
                name = name.upper()
            elif deco_id == "l":
                if not runtime_mode:
                    continue
                name = name.lower()
            elif deco_id == "c2s":
                if not runtime_mode:
                    continue
                name = re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
            elif deco_id =="pre":
                if not runtime_mode:
                    continue
                name = splits[1] + name
            elif deco_id =="store":
                if not runtime_mode:
                    continue
                store_name = splits[1]
                self.ctx.ttg.set_scoped_value(store_name,name)                
            elif deco_id =="lstore":
                if not runtime_mode:
                    continue                
                store_list_name = splits[1]
                self.ctx.store_to_list(store_list_name,name)                
            elif deco_id =="lget":
                if not runtime_mode:
                    continue
                lget_splits = splits[1].split(",")
                store_name=lget_splits[0]
                store_list = self.ctx.get_store_list(store_name)
                if not store_list:
                    print("Unknown store list! %s[%s]" % (store_name,decorator))
                    os.abort()
                store_delimiter = ","
                if len(lget_splits)>1:
                    store_delimiter=lget_splits[1]
                    if store_delimiter=="comma":
                        store_delimiter=","
                name = store_delimiter.join(store_list)
            elif deco_id =="echo":
                if not runtime_mode:
                    continue
                echo_splits = splits[1].split(',')
                echo_output = echo_splits[0]
                vars = ()
                for var in echo_splits[1:]:
                    if var.startswith("@idx"):
                        data = var.split('#',1)
                        if len(data)==1:
                            vars+=(self.ctx.current_xml_idx,)
                        else:
                            vars+=(self.ctx.current_xml_tag_idx[data[1]],)
                    elif var=="@":
                        vars+=(name,)
                    elif var=="@current":
                        vars+=(self.default_value,)
                    elif var.startswith("@"):
                        name_scope,name_name,name_decos=get_scope_and_name(var[1:])
                        value = self.ctx.ttg.get_scoped_value(name_scope,name_name)
                        if not value:
                            print("ABORT: unknown echo variable:%s in '%s'" % (var,decorator))
                            os.abort()
                        vars+=(value,)
                    else:
                        vars+=(var,)
                name = echo_output % vars
            elif deco_id =="post":
                if not runtime_mode:
                    continue
                name = name + splits[1]
            elif deco_id =="post_n_blast":
                if not runtime_mode:
                    continue

                data = splits[1].split(',',1)
                
                elem_length = self.ctx.current_xml_len
                elem_idx = self.ctx.current_xml_idx
                output = None
                if len(data)>1:
                    if data[0]!="" and data[1]!="":
                        output=data[0]
                        try:
                            elem_length = self.ctx.current_xml_tag_len[data[1]]
                            elem_idx = self.ctx.current_xml_tag_idx[data[1]]
                        except:
                            print("unknown tag-filter:%s setting len=0" % data[1])
                            elem_length = 0
                            elem_idx = 0
                    else:
                        output=splits[1]
                else:
                    output=splits[1]
                
                if output=="comma":
                    output=","

                if elem_idx+1 < elem_length:
                    name = name + output
            elif deco_id =="debug":
                debug_id = splits[1]
                if debug_id=="struct" and "[" in name:
                    a=0
            elif deco_id =="required":
                if runtime_mode:
                    continue
                self.required=True
            elif deco_id == "replace":
                if not runtime_mode:
                    continue
                info = splits[1].split(",")
                name = name.replace(info[0],info[1])
            elif deco_id =="default":
                name = self.default_value
            elif deco_id == "map":
                if runtime_mode:
                    continue
                mapname,varkey = splits[1].split(",")
                self.ctx.add_map_value(mapname,varkey,self.default_value)
            elif deco_id == "getmap":
                if not runtime_mode:
                    continue

                info = splits[1].split(",")
                mapname = info[0]
                var = info[1]
                default = self.default_value
                if len(info)>2:
                    default=info[2]

                var = self.ctx.resolve_var(var,name,default)
                
                # if var=="@":
                #     var=name
                # elif var.startswith("@"):
                #     name_scope,name_name,name_decos=get_scope_and_name(var[1:])
                #     value = self.ctx.ttg.get_scoped_value(name_scope,name_name)
                #     if not value:
                #         print("ABORT: unknown echo variable:%s in '%s'" % (var,decorator))
                #         os.abort()
                #     var=value

                name = self.ctx.get_map_value(mapname,var,default)
            elif deco_id == "if":
                if not runtime_mode:
                    continue
                infos = splits[1].split(",")
                condition = infos[0]
                if_true = None
                if_false = None
                if len(infos)>1:
                    if_true=infos[1]
                    if if_true=="@current":
                        if_true=self.default_value
                if len(infos)>2:
                    if_false=infos[2]
                    if if_false=="@current":
                        if_false=self.default_value
                
                while (True):
                    res=re.match("(\\@[a-zA-Z_]+)",condition)
                    if not res:
                        break
                    var = res.group(1)
                    if var=="@current":
                        var=self.default_value
                    varResult = self.ctx.resolve_var(var,'NONE','None')
                    
                    try:
                        number=int(varResult)
                        condition=condition.replace(var,"%s"%varResult)
                    except:
                        if varResult=="None":
                            condition=condition.replace(var,"None")
                        else:
                            condition=condition.replace(var,"'%s'"%varResult)

                condResult = eval(condition)

                if condResult:
                    name = if_true
                else:
                    name = if_false

            

            # TODO: implement this:
            # elif deco_id=="ifnset" or deco_id=="ifset":
            #     is_equalcheck = deco_id=="ifset"
            #     if not runtime:
            #         continue
            #     vals = splits[1].split(',')
            #     varname = None
            #     ifblock = -1
            #     varvalue = None
            #     if len(vals)==1:
            #         varname=vals[0]
            #     elif len(vals)==2:
            #         varname=vals[0]
            #         varvalue=vals[1]
            #     elif len(vals)==3:
            #         varname=vals[1]
            #         varvalue=vals[2]
            #         ifblock=int(vals[0])
            elif deco_id =="enum":
                info = splits[1].split(",")
                
                enum_item_name=None
                enum_name=None

                if len(info)==1:
                    enum_name=info[0]
                else:
                    enum_item_name=info[0]
                    enum_name=info[1]

                if not runtime_mode:
                    self.enum_type=enum_name
                    if enum_item_name:
                        self.ctx.add_enum(enum_name,enum_item_name,self.default_value)
                    else:
                        # ignore add_enum for this decorator as it is just reading the enum
                        pass
                else:
                    value = self.ctx.get_enum_item(enum_name,name)
                    if value: 
                        name = self.ctx.get_enum_item(enum_name,name)
                    else:
                        if not self.ctx.is_enum_strict(enum_name):
                            #unknown type but its ok because not strict
                            pass
                        else:
                            print ("Unknown enum-item:%s" % name)
                            name = "UNKNOWN"
            elif deco_id =="enum_strict":
                enum_name=splits[1]

                if not runtime_mode:
                    self.ctx.set_enum_strict(enum_name)

            elif deco_id=="enum_add":
                enum_name=splits[1]
                if not self.ctx.runtime_mode:
                    continue
                self.ctx.add_enum(enum_name,name,name)
                
                
            elif deco_id=="enum_mod":
            # e.g. for default modification:
            # enum_mod:type,float,%sf    <--append f
            # enum_mod:type,string,"%s"  <--wrap in dquotes
                if not self.ctx.runtime_mode:
                    continue

                enum_tag,enum_type,pattern=splits[1].split(",")
                name_scope,name_name,name_decos = get_scope_and_name(enum_tag)
                value = self.ctx.ttg.get_scoped_value(name_scope,name_name)
                if value==enum_type:
                    name = pattern % (name,)
                    continue
            else:
                print("Unsupported decorator:%s for name %s" % (decorator,self.name) )
                #os.abort("Unsupported decorator:%s for name" % (decorator,self.name) )
        


        return name

    def execute(self, name):
        name = self.apply_decorators(name)
        return name

class TTOutput:
    def __init__(self,output_string):
        split = output_string.split(',')
        self.output_block = split[0]
        try:
            self.attrib,self.attrib_value = split[1].split('==')
        except:
            self.attrib=None
            self.attrib_value=None

    def check(self,xml):
        #TODO: rework this 
        if self.attrib in xml.attrib:
            xml_value = xml.attrib[self.attrib]
            if xml_value!=self.attrib_value:
                return None
        return self.output_block


class TTBlock:


    def __init__(self,block_name,all_lines,inner_lines,ctx):
        self.ctx=ctx
        self.template=ctx.current_template

        bn_splits = block_name.split('|')
        self.block_name=bn_splits[0]
        self.decorators=[]
        if len(bn_splits)>1:
            self.decorators=bn_splits[1:]

        self.all_lines=all_lines
        self.inner_lines=inner_lines

        self.parent_block = None
        self.child_blocks = {}
        self.block_id = C.create_id()
        self.names = {}
        self.outputs = []
        self.conditions = [] # a set of conditions that are required to be true for the block to be shown
        self.filename=None
        self.file_overwrite=False

        self.execute_decorators()

    def check_conditions(self,check_context):
        for condition_check,data in self.conditions:
            result = condition_check(check_context,data)
            if not result:
                return False
        return True

    def merge_block(self,current_struct,scope_dict,layer=0):
        result = '\t'*layer+self.block_name+'\n'
#        result = '\t'*layer+self.block_name

        work_struct=current_struct.get(self.block_name)
        if not work_struct:
            work_struct=current_struct[self.block_name]={"__names":{}}

        name_dict=work_struct["__names"]
        
        for name in self.names:
            name_data = self.names[name][0]

            def is_required_name(name):
                for n in self.names[name]:
                    if n.required:
                        return True
                return False

            # check if any of the names is required. 
            name_data.required = is_required_name(name_data.name)

            if name_data.has_scope():
                last_block = name_data.scope.split('.').pop()
                scope_struct=scope_dict.get(last_block)
                if scope_struct and name not in scope_struct["__names"]:
                    scope_struct["__names"][name]=name_data
            elif name not in name_dict or name_data.required:
                name_dict[name]=name_data

        for blockName in self.child_blocks:
            block_list = self.child_blocks[blockName]
            for inner_block in block_list:
                scope_dict[self.block_name]=work_struct
                result += inner_block.merge_block(work_struct,scope_dict,layer+1)
                scope_dict.pop(self.block_name,None)

        return result


    def execute_decorators(self,runtime=None):
        for decorator in self.decorators:
            splits=decorator.split(":")
            deco_id=splits[0].lower()

            if deco_id=="output":
                output=TTOutput(splits[1])
                self.outputs.append(output)
            elif deco_id=="overwrite":
                if runtime:
                    continue
                self.file_overwrite=True
            elif deco_id=="file":
                if not runtime:
                    continue

                file_splits = splits[1].split(',')
                filenameString = file_splits[0]
                vars = ()
                for var in file_splits[1:]:
                    name_scope,name_name,name_decos=get_scope_and_name(var)
                    value = self.ctx.ttg.get_scoped_value(name_scope,name_name)
                    vars+=(value,)

                self.filename = filenameString % vars
            elif deco_id=="else":
                if not runtime:
                    ifblock=-1
                    try:
                        ifblock = int(splits[1])
                    except:
                        pass

                    def check(check_context,data):
                        ifblock = data[0]
                        if check_context["ifblocks"][ifblock]==True:
                                # this block is already resolved
                            return False
                        if ifblock!=-1:
                            check_context["ifblocks"][ifblock]=True
                        return True
                    self.conditions.append((check,(ifblock,)))
                                                            
            elif deco_id=="ifnset" or deco_id=="ifset":
                is_equalcheck = deco_id=="ifset"
                if not runtime:
                    vals = splits[1].split(',')
                    varname = None
                    ifblock = -1
                    varvalue = None
                    if len(vals)==1:
                        varname=vals[0]
                    elif len(vals)==2:
                        varname=vals[0]
                        varvalue=vals[1]
                    elif len(vals)==3:
                        varname=vals[1]
                        varvalue=vals[2]
                        ifblock=int(vals[0])

                    def check(check_context,data):
                        varname,ifblock,varvalue=data
                        try:
                            if check_context["ifblocks"][ifblock]==True:
                                # this if block is already resolved
                                return False
                        except:
                            # this block seems to be not resolved,yet
                            pass

                        name_scope,name_name,name_decos=get_scope_and_name(varname)
                        value = self.ctx.ttg.get_scoped_value(name_scope,name_name,check_context["xml_current"])
                        
                        result = None
                        if is_equalcheck:
                            result = (varvalue is None and value is not None) or (varvalue and value==varvalue)
                        else:
                            result = (varvalue is None and value is None) or (varvalue and value!=varvalue)
                        
                        if result and ifblock!=-1:
                            # tell the check-context that this ifblock is resolved and upcoming checks should result in false
                            check_context["ifblocks"][ifblock]=True

                        return result

                                        
                    self.conditions.append((check,(varname,ifblock,varvalue)))


    def add_block(self,block):
        if block.block_name not in self.child_blocks:
            self.child_blocks[block.block_name]=[]
            self.template.blocks[block.block_name]=self.child_blocks[block.block_name]

        self.child_blocks[block.block_name].append(block)

    def has_block_with_name(self,blockname):
        return blockname in self.child_blocks   

    def get_block_with_name(self,blockname):
        if not self.has_block_with_name(blockname):
            return None
        return self.child_blocks[blockname]

    def set_parent(self,block):
        self.parent_block=block

    def get_marker(self,xml=None):
        if xml is not None:
            for output in self.outputs:
                output_block = output.check(xml)
                if output_block:
                    try:
                        alternative_outputs = self.template.blocks[output_block]
                        if len(alternative_outputs)>1:
                            os.abort("Alternative output:%s must be unique" % output_block)
                        
                        alternative_output = alternative_outputs[0]
                        return alternative_output.get_marker(xml)
                    except:
                        os.abort("Alternative output:%s must be present in ctx" % output_block)

        return "|<#%s#>|" % self.block_id

    def find_name(self,text):
        p = ("%s(name|N):(.*?)%s(.*?)%s(EN|endname)%s") % (C.delimiter_start,C.delimiter_end,C.delimiter_start,C.delimiter_end)
#        res = re.search( p,text,re.MULTILINE | re.DOTALL)
        res = re.search( p,text)
        return res

    def process_names(self):
        while True:
            res = self.find_name(self.inner_lines)
            if not res:
                break

            name_all = res.group(0)
            name_data = res.group(2)

            # check for scopes
            name_scope,name_name,name_decos = get_scope_and_name(name_data)

            name_default = res.group(3)
            name_with_decos = name_name
            if name_decos:
                name_with_decos+=name_decos

            name = TTName(name_with_decos,name_default,self.ctx,name_scope)
            self.inner_lines = self.inner_lines.replace(name_all,name.get_marker(),1)
            
            if name.name not in self.names:
                self.names[name.name]=[]
            self.names[name.name].append(name)
            
            print(all)

    def has_name(self,name):
        return name in self.names

    def execute_name(self,_name,value,input_text,ctx,include_scoped=True):
        if not self.has_name(_name):
            return input_text
        
        for name in self.names[_name]:
            if not include_scoped and name.has_scope():
                continue
            name_result = name.execute(value)
            if name_result is None:
                name_result = name.execute(value)
                name_result = "(ERROR:%s)"%name
            name_marker = name.get_marker()
            input_text = input_text.replace(name_marker,name_result)

        return input_text


class TTTemplate:
    def __init__(self,name):
        self.root_block=None
        self.blocks={}
        self.name=name

    def set_root_block(self,block):
        self.root_block=block

    def get_root_block(self):
        return self.root_block



class ParseContext:
    def __init__(self):
        self.current_block=None
        self.current_template=None
        self.current_scope=None
        self.current_xmlscope=None
        self.enums={}
        self.strict_enums={}
        self.maps={}
        self.templates={}
        self.xml_current=None
        self.xml_root=None
        self.ttg = None
        self.runtime_mode = False
        self.current_xml_len = None
        self.current_xml_idx = None
        self.current_xml_tag_idx = {}
        self.current_xml_tag_len = {}
        self.stored_lists = None
    
    def count_and_init_xml_tag_length(self,xmlblock):
        for xml in xmlblock:
            current_tag = strip_tag(xml.tag)
            if current_tag not in self.current_xml_tag_len:
                self.current_xml_tag_len[current_tag]=1
                self.current_xml_tag_idx[current_tag]=-1 # init with -1 due to starting with increment =>0
            else:
                self.current_xml_tag_len[current_tag]+=1
    
    #untested
    def amount_tags_in_xml(self,xmlblock,tag):
        amount=0
        for xml in xmlblock:
            current_tag = strip_tag(xml.tag)
            if (current_tag==tag):
                amount+=1
        return amount

    def store_to_list(self,list_name,value):
        if not self.stored_lists:
            self.stored_lists = {}
        
        list = self.stored_lists.get(list_name)
        if not list:
            self.stored_lists[list_name]=list=[]
        
        list.append(value)
        return list
        
    def get_store_list(self,list_name):
        if not self.stored_lists:
            return None
        
        result = self.stored_lists.get(list_name)
        return result

    def add_map_value(self,mapname,varkey,value):
        map = self.maps.get(mapname)
        if not map:
            map = self.maps[mapname] = {}
        map[varkey]=value

    def get_map_value(self, mapname, varkey,default):
        try:
            return self.maps[mapname][varkey]
        except:
            if verbose:
                print("Unknown map-lookup: %s:%s" % (mapname,varkey))
            return default

    def add_enum(self,enum_name,item_name,mapping_name):
        if enum_name not in self.enums:
            self.enums[enum_name]={}

        enum = self.enums[enum_name]
        if item_name in enum and enum[item_name]!=mapping_name:
            print("enum mismatch for enum %s: item-name: %s. Wanted to set new not matching mapping! before: %s new: %s" % (enum_name,item_name,enum[item_name],mapping_name))
            os.abort()

        enum[item_name]=mapping_name

    def set_enum_strict(self,enum_name):
        if enum_name not in self.strict_enums:
            self.strict_enums[enum_name]=True
    
    def is_enum_strict(self,enum_name):
        return enum_name in self.strict_enums

    def get_enum(self,enum_name):
        if not enum_name in self.enums:
            return None
        enum = self.enums[enum_name]
        return enum

    def get_enum_item(self,enum_name,item_name):
        enum = self.get_enum(enum_name)

        if not enum or not item_name in enum:
            return None
        
        return enum[item_name]    

    def resolve_var(self,var,current,default):
        if var=="@":
            return current
        elif var.startswith("@"):
            name_scope,name_name,name_decos=get_scope_and_name(var[1:])
            value = self.ttg.get_scoped_value(name_scope,name_name)
            if value is not None:
                return value

        return default


    # def find_block_in_scope(self,blockname):
    #     block_splits = blockname.split('.')
        
    #     current = block_splits.pop(0)
    #     found_start = False
    #     # find beginning
    #     for scope in self.current_scope:
    #         if scope.block_name==current:
    #             if not found_start:
    #                 found_start=True
                
    #             if not block_splits:
    #                 return scope

    #             current=block_splits.pop(0)
    #         else:
    #             if found_start:
    #                 return None
        
    #     return None


class TTGenerator:
    def __init__(self, config_filepath,args):
        C.args=args
        C.config_file_path = os.path.abspath(config_filepath)
        C.config_folder = os.path.dirname(C.config_file_path)

        self.current_template = None
        self.ctx = None

        def resolve_values(value):
            value_type = type(value)
            if value_type is str:
                value = value.replace("${configfolder}",C.config_folder)
            elif value_type is list:
                for i in range(len(value)):
                    value[i]=resolve_values(value[i])
            return value


        try:
            file_exists = os.path.isfile(C.config_file_path)
            file = open(C.config_file_path)
            data = file.read() 
            file.close()
            C.config = json.load(open(C.config_file_path))
            if "config" in C.config:
                confs = C.config["config"]
                for key in confs:
                    value = confs[key]
                    old_key=key
                    key = key.replace("-","_")
                    value=resolve_values(value)
                    if hasattr(args,key):
                        setattr(args,key,value)
                    else:
                        print("unknown config: %s:%s" %(old_key,value))
                        setattr(args,key,value)
            if "templates" not in C.config:
                C.config["templates"]=[]
            self.load_imports()


        except Exception as e: # work on python 3.x
            print("Could not find configuration-file:%s\nexception:%s" % (C.config_file_path,str(e)))
            os.abort()

        self.create_default_configs()
#        self.parseTemplates()

    def load_imports(self):
        if "imports" in C.config:
            for import_path in C.config['imports']:
                # include all templates of the imports as well
                try:
                    import_path = C.config_folder+"/"+import_path
                    import_folder = os.path.dirname(import_path)
                    print("import config:%s" % import_path)
                    ijson = json.load(open(import_path))
                    if "templates" in ijson:
                        orig_templates = C.config["templates"]
                        for i_template in ijson["templates"]:
                            newpath = import_folder+"/"+i_template["path"]
                            if os.path.isfile(newpath):
                                i_template["path"]=newpath
                                orig_templates.append(i_template)    
                            else:
                                print("Unknown file as imported template:%s" % newpath)
                except Exception as e:
                    print("Could not load IMPORT-JSON:%s" % import_path)
                 


    def check_default(self,json,key,defaultvalue):
        if key not in json:
            json[key]=defaultvalue

    def create_default_configs(self):
        self.check_default(C.config,C.CONFIG_COMMENT_START,"/*")
        self.check_default(C.config,C.CONFIG_COMMENT_END,"*/")

        C.delimiter_start=re.escape(C.config[C.CONFIG_COMMENT_START])
        C.delimiter_end=re.escape(C.config[C.CONFIG_COMMENT_END])
        C.rootname=C.config[C.CONFIG_ROOT_NAME] or "root"

        self.token_block_begin_any = "%s(B|block):(.*?)%s" % (C.delimiter_start,C.delimiter_end)
        self.token_block_end_any = "%s(EB|endblock):(.*?)%s" % (C.delimiter_start,C.delimiter_end)

    def re_find_full_block(self,blockname,text):
        blockname_splits=blockname.split('|')
        blockname_simple=blockname_splits[0]
        blockname=re.escape(blockname)
        p = ("%s(B|block):%s%s(.*?)%s(EB|endblock):%s%s") % (C.delimiter_start,blockname,C.delimiter_end,C.delimiter_start,blockname_simple,C.delimiter_end)
        print("Find full block for blockname:%s with pattern %s" % (blockname,p) )
        res = re.search( p,text,re.MULTILINE | re.DOTALL)
        return res

    def parseTemplates(self):
        self.ctx = ParseContext()
        self.ctx.ttg = self

        for template in C.config[C.CONFIG_TEMPLATES]:
            template_name = template["name"]
            template_path = template["path"]
            if not os.path.isabs(template_path):
                template_path = C.config_folder+"/"+template_path
            
            if not os.path.isfile(template_path):
                sys.exit("Unknown template:"+template_path)
            
            with open(template_path) as f:
                lines = f.read()
                self.ctx.current_template=_template=template["template"]=TTTemplate(template_name)
                self.ctx.templates[template_name]=_template
                root_block = self.parseTemplate(self.ctx,lines)
                _template.set_root_block(root_block)

    def generateXSD(self,xsd_name):
        namespace="https://%s.com" % xsd_name
        data_struct = {}

        # merge structs from all templates
        for template in C.config[C.CONFIG_TEMPLATES]:
            _template=template["template"]
            template_name = template["name"]            
            block = _template.get_root_block()
            result = block.merge_block(data_struct,{})
            print("--%s--\n%s"%(template_name,result))

        xml_doc = minidom.Document()
        
        xml_root = xml_doc.createElement("xs:schema")
        xml_root.setAttribute('xmlns:xs','http://www.w3.org/2001/XMLSchema')
        xml_root.setAttribute('targetNamespace',namespace)
        xml_root.setAttribute('xmlns',namespace)
        xml_root.setAttribute('elementFormDefault',"qualified")
        xml_doc.appendChild(xml_root)

        def create_enum_type(xml_doc,xml_root,name,enum_values,strict=False):
		# <xs:union>
		# 	<xs:simpleType>
		# 		<xs:restriction base="xs:string">
		# 			<xs:enumeration value="float"/>
		# 			<xs:enumeration value="int"/>
		# 			<xs:enumeration value="string"/>
		# 		</xs:restriction>
		# 	</xs:simpleType>
		# 	<xs:simpleType>
		# 		<xs:restriction base="xs:string">
		# 		</xs:restriction>
		# 	</xs:simpleType>
		# </xs:union>
            
            enum_type = xml_doc.createElement("xs:simpleType")
            enum_type.setAttribute('name',name)
            enum_type.setAttribute('final','restriction') # what is this for?
            xml_root.appendChild(enum_type)

            current_elem = enum_type

            if not strict:
                union = xml_doc.createElement("xs:union")
                string_type = xml_doc.createElement("xs:simpleType")

                enum_restriction = xml_doc.createElement("xs:restriction")
                enum_restriction.setAttribute("base","xs:string")
                string_type.appendChild(enum_restriction)
                union.appendChild(string_type)

                enum_inner_type = xml_doc.createElement("xs:simpleType")
                union.appendChild(enum_inner_type)
                
                current_elem = enum_inner_type
                enum_type.appendChild(union)

            enum_restriction = xml_doc.createElement("xs:restriction")
            enum_restriction.setAttribute("base","xs:string")
            current_elem.appendChild(enum_restriction)

            for value in enum_values:
                enum_value = xml_doc.createElement("xs:enumeration")
                enum_value.setAttribute("value",value)
                enum_restriction.appendChild(enum_value)

            return enum_type

        def create_xsd_for_struct(elem_name,current_struct,xml_doc,xml_current):
            xml_elem = xml_doc.createElement("xs:element")
            xml_elem.setAttribute("name",elem_name)

            xml_current.appendChild(xml_elem)
            xml_current = xml_elem

            xml_complex = xml_doc.createElement("xs:complexType")
            xml_current.appendChild(xml_complex)
            xml_current = xml_complex

            # add names as xml-attribute
            current_names = current_struct["__names"]
            names = sorted(current_names.keys())

            # now process nested structs                
            if len(current_struct)>1:
                xml_choice = xml_doc.createElement("xs:choice")
                xml_choice.setAttribute("minOccurs","0")
                xml_choice.setAttribute("maxOccurs","unbounded")
                xml_current.appendChild(xml_choice)
                xml_current = xml_choice

                for tag in sorted(current_struct.keys()):
                    if tag=="__names":
                        continue
                    struct = current_struct[tag]
                    create_xsd_for_struct(tag,struct,xml_doc,xml_current)

            for name in names:
                name_data = current_names[name]
                
                name_type = name_data.get_enum_type() or "xs:string"

                xml_attrib = xml_doc.createElement("xs:attribute")
                xml_attrib.setAttribute("name",name)
                xml_attrib.setAttribute("type",name_type)
                if name_data.required:
                    xml_attrib.setAttribute("use","required")

                # TODO: required
                xml_complex.appendChild(xml_attrib)

        # create enum-types in xml
        for enum_name in self.ctx.enums:
            enum = self.ctx.enums[enum_name]
            sorted_keys = sorted(enum.keys())
            create_enum_type(xml_doc,xml_root,enum_name,sorted_keys,self.ctx.is_enum_strict(enum_name))

        #iterate of structs
        for struct_name in sorted(data_struct.keys()):
            struct=data_struct[struct_name]
            create_xsd_for_struct(struct_name,struct,xml_doc,xml_root)

        xsd_result = xml_doc.toprettyxml()
        #print("STRUCT:%s" % data_struct)
        #print("XSD: %s" % xsd_result)
        return xsd_result

    def parseTemplate(self,ctx,lines):
        root_block=TTBlock(C.rootname,lines,lines,ctx)
        allblocks=[root_block]
        allblocks=self.parseBlocks(root_block,lines,allblocks)

        for block in allblocks:
            block.process_names()

        return root_block

    def parseBlocks(self,current_block,lines,allblocks=None):
        # parse blocks
        allblocks = allblocks or []
        while True:

            # find start-block
            result = re.search(self.token_block_begin_any,lines)
            if not result:
                break

            block_name=result.group(2)

            # find corresponding endblock
            result = self.re_find_full_block(block_name,lines)

            if not result:
                print("Could not find ENDBLOCK for %s" %block_name)
                return allblocks

            all = result.group(0)
            innertext = result.group(2)
            block = TTBlock(block_name,all,innertext,self.ctx)
            allblocks.append(block)

            if current_block:
                current_block.add_block(block)
                block.set_parent(current_block)
            
            # strip the block-content form the overall lines
            lines = lines.replace(all,block.get_marker(),1)
            current_block.inner_lines=lines

            # recurse into the just created block
            allblocks=self.parseBlocks(block,innertext,allblocks)
        
        return allblocks

    def executeFromFile(self,xml_data_path,config=None):
        self.ctx.runtime_mode=True
        # TODO: combine configs somehow

        # load xml-file as string
        file = io.open(xml_data_path)
        stXmlFile = file.read()
        file.close()

        # convert xml-string to be xml-compliant (e.g. change <bla src="List<string>"/>  to "List&lt;string&gt;"  )
        result = convert_to_valid_xml(stXmlFile)

        tree = ET.ElementTree(ET.fromstring(result))
        root = tree.getroot()
        return self.executeFromXml(root)

    def executeFromXml(self,root):
        self.ctx.xml_root=root
        self.ctx.xml_current=root
        result={}
        template_results=[]


        
        tag = strip_tag(root.tag)
        if tag==C.rootname:
            for template in C.config[C.CONFIG_TEMPLATES]:
                template_result = self.executeTemplate(template["template"],root)
                template_results.append({"template":template,"result":template_result})
        result["template_results"]=template_results
        result["context"]=self.ctx
        return result

    def find_xml_for_scope(self,scope_signature,ctx=None):
        if not scope_signature:
            return ctx or self.ctx.xml_current

        ctx = ctx or self.ctx

        if type(scope_signature)==ET.Element:
            return scope_signature    

        block_splits = scope_signature.split('.')
        block_splits.reverse()
        
        current = block_splits.pop(0)
        xml_scope = []+ctx.current_xmlscope
        xml_scope.reverse()

        found_start = False
        # find beginning
        while True:
            current_xml = xml_scope.pop(0)            
            current_tag = strip_tag(current_xml.tag)
            if current_tag==current:
                if not found_start:
                    found_start=True
                
                if not block_splits:
                    return current_xml

                current=block_splits.pop(0)
            else:
                if found_start:
                    return None
            
        return None

    def get_scoped_value(self,scope,key,ctx=None):
        if not key:
            scope_splits = scope.split('.')
        
        scope_xml = self.find_xml_for_scope(scope,ctx)
        if scope_xml is not None:
            try:
                value = scope_xml.attrib[key]        
                return value
            except:
                return None
        else:
            os.abort("Unknown scope in scoped value  [%s.]%s" % (scope,key))

    def set_scoped_value(self,key,value):
        scope,name,deco = get_scope_and_name(key)
        if not scope:
            self.ctx.xml_current.set(name,value)
        else:
            a=0

    def executeTemplate(self,template,xml,current_result=None,current_blocks=None,calllist=None):
        current_tag = strip_tag(xml.tag)

        self.ctx.xml_current=xml
        block_markers=[]
        if not current_blocks:
            current_blocks = [template.get_root_block()]
            current_result = current_blocks[0].inner_lines
            calllist=[]
            self.ctx.current_xmlscope=[xml]

        # inject block data into 'current_result' but add the blockmarker again at the end for multiple block usage
        block_check_context={
            "blocks":current_blocks,
            "xml_current":self.ctx.xml_current,
            "context" : self.ctx,
            "ifblocks" : {}
        }
        for current_block in current_blocks:
            block_marker = current_block.get_marker(xml)
#            current_result = current_result.replace(block_marker,current_block.inner_lines+"\n"+block_marker) 
            block_check_context["current_block"]=current_block
            check_conditions = current_block.check_conditions(block_check_context)
            if not check_conditions:
                # ignore block due to not all conditions are true
                continue

            current_result = current_result.replace(block_marker,current_block.inner_lines+block_marker) 

            inner_markers = re.findall( "\|<#.*?#>\|",current_block.inner_lines,re.MULTILINE | re.DOTALL)
            if inner_markers:
                for imarker in inner_markers:
                    if imarker not in block_markers:
                        block_markers.append(imarker)
                    

            # try to fill in names
            execute_names = xml.attrib.copy()
            for attrib_key in execute_names:
                attrib_value=xml.attrib[attrib_key]
                # replace name-markers with the attrib value
                current_result = current_block.execute_name(attrib_key,attrib_value,current_result,self.ctx,False)

            # scoped names
            for stName in current_block.names:
                names = current_block.names[stName]
                for name in names:
                    # scoped names
                    if name.has_scope():
                        value = self.get_scoped_value(name.scope,name.name)
                        scope_result = ""
                        # TODO: maybe we want in the None-case something like default values or such? maybe a decorator for that?
                        if value is not None:
                            scope_result = name.execute(value)
                        current_result = current_result.replace(name.get_marker(),scope_result)
                    # auto-names
                    if name not in execute_names and name.has_decorator("auto"):
                        current_result = current_block.execute_name(name.name,name.default_value,current_result,self.ctx,False)


            current_block.execute_decorators(True)

            # block-process
            before_current_xml_len=self.ctx.current_xml_len
            before_current_xml_idx=self.ctx.current_xml_idx
            before_current_xml_tag_idx = self.ctx.current_xml_tag_idx
            before_current_xml_tag_len = self.ctx.current_xml_tag_len
            self.ctx.current_xml_tag_idx = {}
            self.ctx.current_xml_tag_len = {}            
            idx=0
            self.ctx.count_and_init_xml_tag_length(xml)
            for xml_child in xml:
                child_tag = strip_tag(xml_child.tag)
                self.ctx.current_xml_tag_idx[child_tag]+=1

                new_blocks = current_block.get_block_with_name(child_tag)
                if new_blocks:
                    calllist.append(current_block)
                    self.ctx.current_xmlscope.append(xml_child)
                    self.ctx.current_scope=calllist
                    self.ctx.current_xml_idx=idx
                    try:
                        self.ctx.current_xml_len=len(xml)
                    except:
                        self.ctx.current_xml_len=0
                    current_result = self.executeTemplate(template,xml_child,current_result,new_blocks,calllist)
                    calllist.remove(current_block)
                    self.ctx.current_xmlscope.remove(xml_child)
                idx+=1

            self.ctx.current_xml_len = before_current_xml_len
            self.ctx.current_xml_idx = before_current_xml_idx
            self.ctx.current_xml_tag_idx = before_current_xml_tag_idx
            self.ctx.current_xml_tag_len = before_current_xml_tag_len


        # remove markers added by this block
        a=0
        for marker in block_markers:
            current_result=current_result.replace(marker,"")

        if current_block.filename:
            current_result = current_result.replace(block_marker,"")
            output_filename = "%s/%s" %(generation_root,current_block.filename)
            # remove markers
            # TODO: actually there shouldn't be an left,right? Check this
            current_result = re.sub(marker_pattern,"",current_result)
            # stash multiple newlines to one
            current_result = re.sub(r'\n\s*\n', '\n\n', current_result)            
            if current_block.file_overwrite or option_force_overwrite or not os.path.isfile(output_filename):
                # save this block as dedicated file and do not include to result
                f = open(output_filename,"w")
                f.write(current_result)
                f.close()
            return block_marker
        else:
            return current_result

import argparse
parser = argparse.ArgumentParser(description='Add some integers.')
# parser.add_argument('integers', metavar='N', type=int, nargs='+',
#                     help='interger list')
                    
parser.add_argument('--config-file', type=str, 
                    help='path to dtGen-configuration-file',required=True)
parser.add_argument('--gen-input-file', action="append",
                    help='path to generation input-data-file. (multiple usages possible)')
parser.add_argument('--gen-root-folder', type=str, default="./generated",
                    help='output root path for generated files')

parser.add_argument('--gen-force-overwrite', type=bool,default=False,help="[WARNING] force generation of files that usually would not overwrite existing files")

parser.add_argument('--verbose', type=bool,default=False,help="verbose mode")

parser.add_argument('--xsd-schema-name', type=str, default="dtGen",
                    help='name of the schema')
parser.add_argument('--xsd-output', type=str, 
                    help='path to xsd output-file') 

parser.add_argument('--gen-inputfile-if-missing',type=bool,help='if the specified input xml-file (--gen-input-file) is not present, create a boilerplate.xml')                  
parser.add_argument('--start-runtime',type=bool,help="start runtime to automatically track modified files and generate specific data")
args = parser.parse_args()


gen = TTGenerator(args.config_file,args)
gen.parseTemplates()

has_input_files = hasattr(args,"gen_input_file") and args.gen_input_file!=None and len(args.gen_input_file)>0
option_force_overwrite = args.gen_force_overwrite
option_gen_inputfile = args.gen_inputfile_if_missing
verbose = args.verbose
start_runtime = args.start_runtime

if verbose:
    print("working-directory: %s" % (os.getcwd()))


did_action = False

if has_input_files:
    # "/home/ttrocha/_dev/projects/python/simplegenerator/clazztest.xml"
    generation_root = os.path.abspath(args.gen_root_folder)
    try:
        os.makedirs(generation_root)
    except:
        pass
    for input_file in args.gen_input_file:
        #input_abs = os.path.abspath(input_file)
        if os.path.exists(input_file):
            result = gen.executeFromFile(input_file)
            results = result["template_results"]
            did_action=True
        else:
            # the input file is not present
            if option_gen_inputfile:
                folder_input_file = os.path.dirname(input_file)
                folder_xsd_output = os.path.dirname(args.xsd_output)
                rel_folder = os.path.relpath(folder_xsd_output,folder_input_file)

                filename_xsd = os.path.basename(args.xsd_output)

                # path to locate xsd within xml-file:
                xml_xsd_path = rel_folder+"/"+filename_xsd

                # create a simple one to have all this xsd-stuff filled out for you
                boilerplate_xml="""<?xml version="1.0"?>

<{0} xmlns="https://{1}.com" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="https://{1}.com {2}">

</{0}>      
                """.format('root',args.xsd_schema_name,xml_xsd_path)
                # write boilerplate
                new_file = open(input_file,"w")
                new_file.write(boilerplate_xml)
                new_file.close()

if hasattr(args,"xsd_output"):
    xsd_schema = gen.generateXSD(args.xsd_schema_name) # clazz
    xsd_file_path = os.path.abspath(args.xsd_output)
    xsd_folder = os.path.dirname(xsd_file_path)
    try:
        os.makedirs(xsd_folder)
    except:
        pass        
    f = open(xsd_file_path,"w")
    f.write(xsd_schema)
    f.truncate()
    f.close()
    did_action=True


if not did_action:
    print("neither --xsd-output nor --input-file were set!!! NOTHING TO DO")    



if start_runtime:
    def on_created(event):
        print(f"hey, {event.src_path} has been created!")    
 
    def on_deleted(event):
        print(f"what the f**k! Someone deleted {event.src_path}!")

    def on_modified(event):
        print(f"hey buddy, {event.src_path} has been modified")

    def on_moved(event):
        print(f"ok ok ok, someone moved {event.src_path} to {event.dest_path}")

    patterns = ["*"]
    ignore_patterns = None
    ignore_directories = False
    case_sensitive = True
    my_event_handler = PatternMatchingEventHandler(patterns, ignore_patterns, ignore_directories, case_sensitive)

    my_event_handler.on_created = on_created
    my_event_handler.on_deleted = on_deleted
    my_event_handler.on_modified = on_modified
    my_event_handler.on_moved = on_moved

    path = "."
    go_recursively = True
    my_observer = Observer()
    my_observer.schedule(my_event_handler, path, recursive=go_recursively)
    my_observer.start()

    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        my_observer.stop()
        my_observer.join()
        

#counter=0
# for result in results:
#     filename = "output%s.h" % counter
#     counter+=1
#     f = open(filename,"w")
#     f.write(result["result"])
#     f.close()
