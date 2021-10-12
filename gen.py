import json,os,sys,re
import xml.etree.ElementTree as ET

def get_scope_and_name(name_data):
    name_name=None
    name_scope=None
    last_dot_pos = name_data.rfind('.')
    if last_dot_pos==-1:
        name_name=name_data
    else:
        name_name=name_data[last_dot_pos+1:]
        name_scope=name_data[:last_dot_pos]  
    return name_scope,name_name  

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
    root_name = None

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

        name_info = data.split('|')
        self.name = name_info[0]

        for i in range(1,len(name_info)):
            self.decorators.append(name_info[i])

        # fake apply for global decorators (enum)
        self.apply_decorators("init")
        # todo: decorators

    def get_marker(self):
        return "|<#%s#>|" % self.name_id

    def has_scope(self):
        return self.scope is not None

    def apply_decorators(self,name):
        for decorator in self.decorators:
            splits = decorator.split(':')
            deco_id = splits[0]

            if deco_id == "fu":
                name = name[0].upper() + name[1:]
            elif deco_id =="pre":
                name = splits[1] + name
            elif deco_id =="post":
                name = name + splits[1]
            elif deco_id =="enum":
                info = splits[1].split(",")
                
                enum_item_name=None
                enum_name=None

                if len(info)==1:
                    enum_name=info[0]
                else:
                    enum_item_name=info[0]
                    enum_name=info[1]

                if name=="init":
                    if enum_item_name:
                        self.ctx.add_enum(enum_name,enum_item_name,self.default_value)
                    else:
                        # ignore add_enum for this decorator as it is just reading the enum
                        pass
                else:
                    name = self.ctx.get_enum(enum_name,name)
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
        self.attrib,self.attrib_value = split[1].split('==')

    def check(self,xml):
        if self.attrib in xml.attrib:
            xml_value = xml.attrib[self.attrib]
            if xml_value==self.attrib_value:
                return self.output_block
        return None

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
        self.filename=None

        self.execute_decorators()
        

    def execute_decorators(self,runtime=None):
        for decorator in self.decorators:
            splits=decorator.split(":")
            deco_id=splits[0]

            if deco_id=="output":
                output=TTOutput(splits[1])
                self.outputs.append(output)
            elif deco_id=="file":
                if not runtime:
                    continue

                file_splits = splits[1].split(',')
                filenameString = file_splits[0]
                vars = ()
                for var in file_splits[1:]:
                    name_scope,name_name=get_scope_and_name(var)
                    value = self.ctx.ttg.get_scoped_value(name_scope,name_name)
                    vars+=(value,)

                self.filename = filenameString % vars

                

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

    def find_command(self,text):
        p = ("%s(cmd|C):(.*?)%s(.*?)%s(endcmd|endname)%s") % (C.delimiter_start,C.delimiter_end,C.delimiter_start,C.delimiter_end)
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
            name_scope,name_name = get_scope_and_name(name_data)

            name_default = res.group(3)

            name = TTName(name_name,name_default,self.ctx,name_scope)
            self.inner_lines = self.inner_lines.replace(name_all,name.get_marker(),1)
            
            if name.name not in self.names:
                self.names[name.name]=[]
            self.names[name.name].append(name)
            
            print(all)

    def has_name(self,name):
        return name in self.names

    def execute_name(self,name,value,input_text,ctx,include_scoped=True):
        if not self.has_name(name):
            return input_text
        
        for name in self.names[name]:
            if not include_scoped and name.has_scope():
                continue
            name_result = name.execute(value)
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
        self.templates={}
        self.xml_current=None
        self.xml_root=None
        self.ttg = None

    def add_enum(self,enum_name,item_name,mapping_name):
        if enum_name not in self.enums:
            self.enums[enum_name]={}

        enum = self.enums[enum_name]
        if item_name in enum and enum[item_name]!=mapping_name:
            os.abort("enum mismatch for enum %s: item-name: %s. Wanted to set new not matching mapping! before: %s new: %s" % (enum_name,item_name,enum[item_name],mapping_name))

        enum[item_name]=mapping_name

    def get_enum(self,enum_name,item_name):
        if not enum_name in self.enums:
            return None
        enum = self.enums[enum_name]
        if not item_name in enum:
            return None
        
        return enum[item_name]    

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
    def __init__(self, config_filepath):
        C.config_file_path = os.path.abspath(config_filepath)
        C.config_folder = os.path.dirname(C.config_file_path)

        self.current_template = None
        self.ctx = None

        C.config = json.load(open(C.config_file_path))
        self.create_default_configs()
        self.parseTemplates()
        
    def check_default(self,json,key,defaultvalue):
        if key not in json:
            json[key]=defaultvalue

    def create_default_configs(self):
        self.check_default(C.config,C.CONFIG_COMMENT_START,"/*")
        self.check_default(C.config,C.CONFIG_COMMENT_END,"*/")

        C.delimiter_start=re.escape(C.config[C.CONFIG_COMMENT_START])
        C.delimiter_end=re.escape(C.config[C.CONFIG_COMMENT_END])
        C.root_name=C.config[C.CONFIG_ROOT_NAME] or "root"

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
            

    def parseTemplate(self,ctx,lines):
        root_block=TTBlock("root",lines,lines,ctx)
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
                print("NO RESULT!?")
                return

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
        # TODO: combine configs somehow
        tree = ET.parse(xml_data_path)
        root = tree.getroot()
        return self.executeFromXml(root)

    def executeFromXml(self,root):
        self.ctx.xml_root=root
        self.ctx.xml_current=root
        result={}
        template_results=[]
        if root.tag==C.root_name:
            for template in C.config[C.CONFIG_TEMPLATES]:
                template_result = self.executeTemplate(template["template"],root)
                template_result = re.sub("\|<#.*?#>\|","",template_result)
                template_results.append({"template":template,"result":template_result})
        result["template_results"]=template_results
        result["context"]=self.ctx
        return result

    def find_xml_for_scope(self,scope_signature):
        if not scope_signature:
            return self.ctx.xml_current

        block_splits = scope_signature.split('.')
        block_splits.reverse()
        
        current = block_splits.pop(0)
        xml_scope = []+self.ctx.current_xmlscope
        xml_scope.reverse()

        found_start = False
        # find beginning
        while True:
            current_xml = xml_scope.pop(0)            
            if current_xml.tag==current:
                if not found_start:
                    found_start=True
                
                if not block_splits:
                    return current_xml

                current=block_splits.pop(0)
            else:
                if found_start:
                    return None
            
        return None

    def get_scoped_value(self,scope,key):
        if not key:
            scope_splits = scope.split('.')
            
        scope_xml = self.find_xml_for_scope(scope)
        if scope_xml:
            value = scope_xml.attrib[key]        
            return value
        else:
            os.abort("Unknown scoped value  [%s.]%s" % (scope,key))

    def executeTemplate(self,template,xml,current_result=None,current_blocks=None,calllist=None):
        current_tag = xml.tag

        self.ctx.xml_current=xml
        block_markers=[]
        if not current_blocks:
            current_blocks = [template.get_root_block()]
            current_result = current_blocks[0].inner_lines
            calllist=[]
            self.ctx.current_xmlscope=[xml]

        # inject block data into 'current_result' but add the blockmarker again at the end for multiple block usage
        for current_block in current_blocks:
            block_marker = current_block.get_marker(xml)
            current_result = current_result.replace(block_marker,current_block.inner_lines+"\n"+block_marker) 

            inner_markers = re.findall( "\|<#.*?#>\|",current_block.inner_lines,re.MULTILINE | re.DOTALL)
            if inner_markers:
                for imarker in inner_markers:
                    if imarker not in block_markers:
                        block_markers.append(imarker)
                    

            # try to fill in names
            for attrib_key in xml.attrib:
                attrib_value=xml.attrib[attrib_key]
                # replace name-markers with the attrib value
                current_result = current_block.execute_name(attrib_key,attrib_value,current_result,self.ctx,False)

            # scoped names
            for stName in current_block.names:
                names = current_block.names[stName]
                for name in names:
                    if name.has_scope():
                        value = self.get_scoped_value(name.scope,name.name)
                        scope_result = name.execute(value)
                        current_result = current_result.replace(name.get_marker(),scope_result)

            current_block.execute_decorators(True)

            for xml_child in xml:
                child_tag = xml_child.tag

                new_blocks = current_block.get_block_with_name(child_tag)
                if new_blocks:
                    calllist.append(current_block)
                    self.ctx.current_xmlscope.append(xml_child)
                    self.ctx.current_scope=calllist
                    current_result = self.executeTemplate(template,xml_child,current_result,new_blocks,calllist)
                    calllist.remove(current_block)
                    self.ctx.current_xmlscope.remove(xml_child)
        
        # remove markers added by this block
        a=0
        for marker in block_markers:
            current_result=current_result.replace(marker,"")

        if current_block.filename:
            # save this block as dedicated file and do not include to result
            current_result = current_result.replace(block_marker,"")
            f = open(current_block.filename,"w")
            f.write(current_result)
            f.close()
            return block_marker
        else:
            return current_result


        
            
        


gen = TTGenerator("sample/config.json")
gen.parseTemplates()

result = gen.executeFromFile("/home/ttrocha/_dev/projects/python/simplegenerator/sample/data.xml")
results = result["template_results"]
counter=0
for result in results:
    filename = "output%s.h" % counter
    counter+=1
    f = open(filename,"w")
    f.write(result["result"])
    f.close()
