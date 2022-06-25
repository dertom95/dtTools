/*block:commands|file:GenCommands.cs*/
using System;
using System.Collections.Generic;
using Leopotam.EcsLite.Net2;
using MessagePack;
/*block:using*/using /*name:name|required*/MessagePack/*endname*/;
using NetworkLayer2;
/*endblock:using*/

namespace /*name:namespace|required*/_CommandStructs/*endname*/
{
    public interface IProtocol {
/*block:command*/        // Command-Id: /*name:commandId|required*/1000/*endname*/ /*name:server|default*/execute on server/*endname*/ /*name:client|default*/execute on client/*endname*/ 
//        public void /*name:name|pre:Cmd*/CmdTestCommand/*endname*/(/*block:field*/ /*name:type*/int/*endname*/ /*name:name|post_n_blast:,*/intValue/*endname*/ /*endblock:field*/ /*block:rip*/ ,float floatValue, string stringValue, TestEnumeration testEnum /*endblock:rip*/);
/*endblock:command*/

        public static void RegisterCommands(EcsIO ecsIO){
            ecsIO
/*block:command*/            .RegisterCommand</*name:name*/TestCommand/*endname*/>(/*name:name|l|pre:cmdid_*/cmdid_testcommand/*endname*/);
/*endblock:command*/
        }

/*block:command*/       const int /*name:name|l|pre:cmdid_*/cmdid_testcommand/*endname*/ = /*name:commandId*/1000/*endname*/;
/*endblock:command*/        
    }

    public class ClientCommands : IProtocol {
        private EcsIO ecsIO;

        public ClientCommands(EcsIO ecsIO){
            this.ecsIO=ecsIO;
        }

/*block:command*/        public void /*name:name|pre:Cmd*/CmdTestCommand/*endname*/(/*block:field*/ /*name:type*/int/*endname*/ /*name:name|post_n_blast:,*/intValue/*endname*/ /*endblock:field*/    /*block:rip*/ ,float floatValue, string stringValue, TestEnumeration testEnum /*endblock:rip*/)
        {            
            var msg = new /*name:name*/TestCommand/*endname*/();
            msg.SetData(/*block:field*/ /*name:name|post_n_blast:,*/intValue/*endname*/ /*endblock:field*/   /*block:rip*/ ,floatValue, stringValue, testEnum/*endblock:rip*/);
            ecsIO.WriteMessage(msg);
        }
/*endblock:command*/        
    }

    public abstract class ServerCommandsBase 
    {
        protected EcsIO ecsIO;
        public ServerCommandsBase(EcsIO ecsIO){
            this.ecsIO = ecsIO;

        }


        public void OnCommand(int cmdId,object obj,IOIdentity ident){
            switch(cmdId){
/*block:command|ifset:server*/                case /*name:commandId*/1000/*endname*/: 
                    var msg = (/*name:name*/TestCommand/*endname*/)obj;
                    /*name:name|pre:Cmd*/CmdTestCommand/*endname*/(/*block:field*/ msg./*name:name*/intValue/*endname*/, /*endblock:field*/   /*block:rip*/msg.floatValue,msg.stringValue,msg.type,/*endblock:rip*/ident);
                    break;
/*endblock:command*/                    
            }
        }
/*block:command*/        public abstract void /*name:name|pre:Cmd*/CmdTestCommand/*endname*/(/*block:field*/ /*name:type*/int/*endname*/ /*name:name|post_n_blast:,*/intValue/*endname*/ /*endblock:field*/    /*block:rip*/ ,float floatValue, string stringValue, TestEnumeration testEnum /*endblock:rip*/,IOIdentity identity);
/*endblock:command*/
    }

    public interface ICopyValues
    {
        void CopyValuesFrom(object obj);
    }

    /*block:command*/
    /*block:enum|ref:types,name*/
    public enum /*name:name|required*/TestEnumeration/*endname*/
    {
        /*block:item*/            
        /*name:name|required*/player/*endname*/ /*name:value|pre:= */= 0/*endname*/,
        /*endblock:item*//*block:rip*/
        coach,
        reporter /*endblock:rip*/
    }
    /*endblock:enum*/

    [MessagePackObject]
    public struct /*name:name|required*/TestCommand/*endname*/ : ICopyValues
    {
        /*block:field*/        /*name:key|echo:[Key(%s)],@*/[Key(0)]/*endname*/ /*name:private|if:@private.lower()=="true",@current,*/[System.NonSerialized]/*endname*/ public /*name:type|required|enum:int,cstype*/int/*endname*/ /*name:name|required*/intValue/*endname*/;
        /*endblock:field*/
        /*block:rip*/
        public /*name:type|enum:float,cstype*/float/*endname*/ floatValue;
        public /*name:type|enum:string,cstype*/string/*endname*/ stringValue;
        public TestEnumeration type;
        /*endblock:rip*/

        public void SetData(/*block:field*/ /*name:type|required|enum:int,cstype*/int/*endname*/ /*name:name|required*/intValue/*endname*/ /*name:default|enum_mod:type,string,"%s"|enum_mod:type,float,%sf|pre:=*/= 1895,/*endname*/ /*name:rip|auto|post_n_blast:,*/ /*endname*/ /*endblock:field*/ /*block:rip*/float floatValue = 18.95f, string stringValue = "f95", TestEnumeration typeValue = TestEnumeration.player/*endblock:rip*/)
        {
            /*block:field*/
            this./*name:name*/intValue/*endname*/ = /*name:name*/intValue/*endname*/;
            /*endblock:field*/
            /*block:rip*/
            this.floatValue = floatValue;
            this.stringValue = stringValue;
            this.type = typeValue;/*endblock:rip*/
        }

        public void CopyValuesFrom(object obj)
        {
            var copyFrom = (/*name:name*/TestCommand/*endname*/)obj;
            SetData(/*block:field*/ /*name:name|pre:copyFrom.|post_n_blast:,*/intValue,/*endname*/ /*endblock:field*/ /*block:rip*/floatValue, stringValue, type/*endblock:rip*/);
        }
    }
    /*endblock:command*/
}
/*endblock:commands*/
