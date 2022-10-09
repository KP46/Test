from flask import Flask, redirect, render_template, request, session
from flask_socketio import SocketIO
from threading import Thread
#from waitress import serve #pip3 install waitress
import datetime

App = Flask(__name__)
App.config['SECRET_KEY'] = 'awhg.verq2zu34.6q3wgev23'
socketio = SocketIO(App, cors_allowed_origins="*")


Players = {} #{SessionID: Player}
Games = {} #{GameID: Game}
WaitingGames = [] #GameIDs

class Player:
    isplaying = False
    iswaiting = False
    isingame = False
    sessionid = None
    session = None
    name = ""
    game = None

    def __init__(self, session):
        self.session= session
        self.name = session['UserName']

    def leavegame(self):
        if self.isingame:
            self.game.leave(self)
            self.game = None
            self.isplaying = False
            self.isingame = False
            self.iswaiting = False

    def joingame(self, GameTags):
        if not self.isingame:
            for ID in WaitingGames:
                This = True
                for Key, Value in GameTags.items():
                    if Games[ID].GameTags.get(Key) != Value:
                        This = False
                        break
                if This:
                    self.game = Games[ID]
                    self.isingame = True
                    break

            if not self.isingame:
                print("CREATING NEW GAME...")
                self.game = Game()
                self.isingame = True
            self.iswaiting = True
            self.game.join(self)

    def gameaction(self, action):
        if self.game == None:
            self.send(['gameover', False])
            return False
        self.game.action(self, action)

    def send(self, Data):
        socketio.send(Data, to=self.sessionid)

    def setplaying(self):
        self.isplaying = True
        self.iswaiting = False

# 1 | 2 | 3 |
#------------
# 4 | 5 | 6 |
#------------
# 7 | 8 | 9 |

class TicTacToe:
    Combinations = [(1, 2, 3), (4, 5, 6), (7, 8, 9), (1, 4, 7), (2, 5, 8), (3, 6, 9), (1, 5, 9), (3, 5, 7)]
    def __init__(self):
        self.Field = {1:None, 2:None, 3:None, 4:None, 5:None, 6:None, 7:None, 8:None, 9:None}

    def action(self, Player, Action):
        if Action['Action'] == 'turn':
            self.turn(Player.session['ID'], Action['Position'])

    def initgame(self):
        self.PlayerTurn = list(self.Players)[0]
        self.Data['Symbols'] = {list(self.Players)[0]:'X', list(self.Players)[1]:'O'}
        list(self.Players.values())[0].send(['initgame', {'rival':list(self.Players.values())[1].name}])
        list(self.Players.values())[1].send(['initgame', {'rival':list(self.Players.values())[0].name}])

    def turn(self, Player, Position):
        if Player == self.PlayerTurn and self.Gameisrunning:
            if self.Field[Position] == None:
                self.Field[Position] = self.PlayerTurn
                self.send(['set', {'position':Position, 'symbol':self.Data['Symbols'][Player]}])
                Winner = self.checkwinner()
                if Winner != None:
                    if Winner == False:
                        Message = ''
                    else:
                        Message = self.Players[Winner].name+' wins!'
                    self.stopgame(Message)
                for User in list(self.Players):
                    if User != self.PlayerTurn:
                        self.PlayerTurn = User
                        break

    def checkwinner(self):
        if None not in self.Field.values():
            return False
        for Combi in self.Combinations:
            if (self.Field[Combi[0]] == self.Field[Combi[1]]) and (self.Field[Combi[1]] == self.Field[Combi[2]]) and self.Field[Combi[0]] != None:
                return self.Field[Combi[0]]

class Game(TicTacToe):
    def __init__(self):
        TicTacToe.__init__(self)
        self.GameID = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        Games[self.GameID] = self
        WaitingGames.append(self.GameID)

        self.GameName = "TicTacToe"
        self.GameTags = {'GameName':self.GameName}
        self.Gameisrunning = False
        self.PlayersNeeded = 2
        self.PlayerCount = 0
        self.Players = {} #{SessionID: Player}
        self.Data = {}

    def join(self, Player):
        self.PlayerCount += 1
        self.Players[Player.session['ID']] = Player
        if self.PlayerCount == self.PlayersNeeded:
            self.startgame()

    def leave(self, Player):
        print("PLAYER:", Player.name, "left the game!")
        self.PlayerCount -= 1
        try: del self.Players[Player.name]
        except: pass
        if self.PlayerCount == 0:
            self.stopgame("Player left the game.")

    def send(self, Data):
        for Player in list(self.Players.values()):
            Player.send(Data)
            
    def startgame(self):
        if self.GameID in WaitingGames:
            WaitingGames.remove(self.GameID)
        if not self.Gameisrunning:
            self.Gameisrunning = True
            self.initgame()
            self.send(['startgame'])

    def stopgame(self, Message): # WIN MESSAGE
        if self.Gameisrunning:
            self.Gameisrunning = False
            self.send(['gameover', Message])
            if self.GameID in WaitingGames:
                WaitingGames.remove(self.GameID)
            for Player in list(self.Players.values()):
                Player.leavegame()
            del Games[self.GameID]
        print(Games, WaitingGames)

@socketio.on('connect')
def connect():
    if Players.get(session.get('ID'), True):
        session['ID'] = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        Players[session['ID']] = Player(session)
    Players[session['ID']].sessionid = request.sid

@socketio.on('disconnect')
def disconnect():
    Players[session['ID']].leavegame()

@socketio.on('message')
def handleData(data):
    print("Received:", data)
    #PlayerPlay
    if data[0] == 'play':
        Players[session['ID']].joingame({'GameName':'TicTacToe'})
        print(len(Games))
    #PlayerLeave
    elif data[0] == 'leave':
        Players[session['ID']].leavegame()
    #PlayerTurn
    elif data[0] == 'gameaction':
        Players[session['ID']].gameaction(data[1])

@App.route("/", methods=['POST', 'GET'])
def IndexRoute():
    Data = {'UserName':session.get('UserName', '')}
    return render_template("Index.html", **Data)

@App.route("/games", methods=['POST', 'GET'])
def GamesRoute():
    Data = {'UserName':session.get('UserName', '')}
    return render_template("Games.html", **Data)

@App.route("/play", methods=['POST', 'GET'])
def PlayRoute():
    if session.get('UserName', '') == '' or request.args.get('UserName', '') != '':
        if request.args.get('UserName', '') == '':
            return redirect('/')
        else: 
            session['UserName'] = request.args['UserName']
    Data = {'SERVERURL':'http://192.168.12.228:80', 'UserName':session['UserName']}
    return render_template("TicTacToe.html", **Data)

App.run(host="0.0.0.0", port=5000, threaded=True)