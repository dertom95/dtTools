
using System;
using System.Collections.Generic;
using Leopotam.EcsLite.Net2;
using MessagePack;

namespace server
{
    public interface IProtocol {
        // Command-Id: 1000 execute on server  
//        public void CmdPing( );
        // Command-Id: 2000  execute on client 
//        public void CmdPong( );

        public static void RegisterCommands(EcsIO ecsIO){
            ecsIO
            .RegisterCommand<Ping>(cmdid_ping);
            .RegisterCommand<Pong>(cmdid_pong);

        }

       const int cmdid_ping = 1000;
       const int cmdid_pong = 2000;

    }

    public class ClientCommands : IProtocol {
        private EcsIO ecsIO;

        public ClientCommands(EcsIO ecsIO){
            this.ecsIO=ecsIO;
        }

        public void CmdPing(    )
        {            
            var msg = new Ping();
            msg.SetData(   );
            ecsIO.WriteMessage(msg);
        }
        public void CmdPong(    )
        {            
            var msg = new Pong();
            msg.SetData(   );
            ecsIO.WriteMessage(msg);
        }

    }

    public abstract class ServerCommandsBase 
    {
        protected EcsIO ecsIO;
        public ServerCommandsBase(EcsIO ecsIO){
            this.ecsIO = ecsIO;

        }

        public void OnCommand(int cmdId,object obj,IOIdentity ident){
            switch(cmdId){
                case 1000: 
                    var msg = (Ping)obj;
                    CmdPing(   ident);
                    break;

            }
        }
        public abstract void CmdPing(    ,IOIdentity identity);
        public abstract void CmdPong(    ,IOIdentity identity);

    }

    public interface ICopyValues
    {
        void CopyValuesFrom(object obj);
    }

    [MessagePackObject]
    public struct Ping : ICopyValues
    {

        public void SetData( )
        {

        }

        public void CopyValuesFrom(object obj)
        {
            var copyFrom = (Ping)obj;
            SetData( );
        }
    }

    [MessagePackObject]
    public struct Pong : ICopyValues
    {

        public void SetData( )
        {

        }

        public void CopyValuesFrom(object obj)
        {
            var copyFrom = (Pong)obj;
            SetData( );
        }
    }

}

