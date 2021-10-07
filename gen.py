import json,os,sys,re
import xml.etree.ElementTree as ET

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
    def __init__(self,data,default_value):
        self.data = data
        self.default_value=default_value
        self.name_id = C.create_id()
        self.decorators=[]

        name_info = data.split('|')
        self.name = name_info[0]

        for i in range(1,len(name_info)):
            self.decorators.append(name_info[i])

        # todo: decorators

    def get_marker(self):
        return "|<#%s#>|" % self.name_id


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
            else:
                print("Unsupported decorator:%s for name %s" % (decorator,self.name) )
                #os.abort("Unsupported decorator:%s for name" % (decorator,self.name) )
        
        return name

    def execute(self, name):
        name = self.apply_decorators(name)
        return name

class TTBlock:


    def __init__(self,block_name,all_lines,inner_lines):
        self.block_name=block_name
        self.all_lines=all_lines
        self.inner_lines=inner_lines

        self.parent_block = None
        self.child_blocks = {}
        self.block_id = C.create_id()
        self.names = {}

    def add_block(self,block):
        if block.block_name not in self.child_blocks:
            self.child_blocks[block.block_name]=[]

        self.child_blocks[block.block_name].append(block)

    def has_block_with_name(self,blockname):
        return blockname in self.child_blocks   

    def get_block_with_name(self,blockname):
        if not self.has_block_with_name(blockname):
            return None
        return self.child_blocks[blockname]

    def set_parent(self,block):
        self.parent_block=block

    def get_marker(self):
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
            name_default = res.group(3)

            name = TTName(name_data,name_default)
            self.inner_lines = self.inner_lines.replace(name_all,name.get_marker(),1)
            
            if name.name not in self.names:
                self.names[name.name]=[]
            self.names[name.name].append(name)
            
            print(all)

    def has_name(self,name):
        return name in self.names

    def execute_name(self,name,value,input_text):
        if not self.has_name(name):
            return input_text
        
        for name in self.names[name]:
            name_result = name.execute(value)
            name_marker = name.get_marker()
            input_text = input_text.replace(name_marker,name_result)

        return input_text


class TTTemplate:
    def __init__(self):
        self.root_block=None

    def set_root_block(self,block):
        self.root_block=block

    def get_root_block(self):
        return self.root_block

class ParseContext:
    def __init__(self):
        self.current_block=None

class TTGenerator:
    def __init__(self, config_filepath):
        C.config_file_path = os.path.abspath(config_filepath)
        C.config_folder = os.path.dirname(C.config_file_path)

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
        p = ("%s(B|block):%s%s(.*?)%s(EB|endblock):%s%s") % (C.delimiter_start,blockname,C.delimiter_end,C.delimiter_start,blockname,C.delimiter_end)
        print("Find full block for blockname:%s with pattern %s" % (blockname,p) )
        res = re.search( p,text,re.MULTILINE | re.DOTALL)
        return res

    def parseTemplates(self):
        ctx = ParseContext()

        for template in C.config[C.CONFIG_TEMPLATES]:
            template_path = template["path"]
            if not os.path.isabs(template_path):
                template_path = C.config_folder+"/"+template_path
            
            if not os.path.isfile(template_path):
                sys.exit("Unknown template:"+template_path)
            
            with open(template_path) as f:
                lines = f.read()
                root_block = self.parseTemplate(template,lines)
                _template=template["template"]=TTTemplate()
                _template.set_root_block(root_block)
            
            print(ctx,lines)

    def parseTemplate(self,template_config,lines):
        root_block=TTBlock("root",lines,lines)
        allblocks=[]
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
            block = TTBlock(block_name,all,innertext)
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
        results=[]
        if root.tag==C.root_name:
            for template in C.config[C.CONFIG_TEMPLATES]:
                result = self.executeTemplate(template["template"],root)
                results.append({"template":template,"result":result})
        return results

    def executeTemplate(self,template,xml,current_result=None,current_blocks=None,calllist=None):
        current_tag = xml.tag

        if not current_blocks:
            current_blocks = [template.get_root_block()]
            current_result = current_blocks[0].inner_lines
            calllist=[]

        # inject block data into 'current_result' but add the blockmarker again at the end for multiple block usage
        for current_block in current_blocks:
            block_marker = current_block.get_marker()
            current_result = current_result.replace(block_marker,current_block.inner_lines+"\n"+block_marker) 

            # try to fill in names
            for attrib_key in xml.attrib:
                attrib_value=xml.attrib[attrib_key]
                # replace name-markers with the attrib value
                current_result = current_block.execute_name(attrib_key,attrib_value,current_result)

            for xml_child in xml:
                child_tag = xml_child.tag

                new_blocks = current_block.get_block_with_name(child_tag)
                if new_blocks:
                    calllist.append(current_block)
                    current_result = self.executeTemplate(template,xml_child,current_result,new_blocks,calllist)
                    calllist.remove(current_block)

        return current_result


        
            
        


gen = TTGenerator("sample/config.json")
gen.parseTemplates()

gen_data = [
    { "class" : 
        {
            "name" : "Exporter",
            "field":  [
                {
                    "name" : "intValue",
                    "type" : "int"
                },
                {
                    "name" : "floatValue",
                    "type" : "float"
                }
            ]
        }
    }
]

results = gen.executeFromFile("/home/ttrocha/_dev/projects/python/simplegenerator/sample/data.xml")

counter=0
for result in results:
    filename = "output%s.h" % counter
    counter+=1
    f = open(filename,"w")
    f.write(result["result"])
    f.close()
