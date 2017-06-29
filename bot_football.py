#* encoding:utf-8 *#

from __future__ import division
import time, math, random
import pygame
import socket_connection_2 as socket_connection
import itertools

import sys
if sys.version >= "3":
    raw_input = input

# je stärker höher die Schusskraft desto größer die maximale Geschossenergie
# schwerere Geschosse, machen mehr schaden aber fliegen langsamer
# wenn zwei Roboter einander verdrängen bleibt der mit mehr Bodenhaftung mehr stehen
# Roboter müssen Batterien sammeln damit ihnen nicht der Strom ausgeht
# sich gegen Umweltprobleme wehren (zB. Regen)
# können sich gegenseitig mit Wasserbomben bewerfen
# können Batterien mit Wasserbomben unbrauchbar machen
# schnellere Features brauchen mehr Energie

def rotary_distance(w1,w2):
    s, b = min(w1,w2), max(w1,w2)
    return min(b-s,s-b+360)

class Field(object):
    def __init__(self):
        self.entities = set()

class BotStats(object):
    # 20 Punkte zu vergeben?
    reload_delay = 0 # 1
    speed = 0
    acceleration = 0
    armor = 0
    throw_power = 0
    static_friction = 100
    dynamic_friction = 50
    mass = 1
    precision = 0
    aufsatz = None #schild, Wurfarm, Greifarm, 

pygame.font.init()
font = pygame.font.Font(None,20)

class Entity(object):
    type = "Entity" # used to choose collision handler
    RADIUS = 0
    pos = (0,0)
    alive = True

    def __init__(self,field):
        self.field = field
        field.entities.add(self)

    def __repr__(self):
        return repr({"type":self.type,
                     "size":self.RADIUS,
                    })

class Bot(Entity):
    type = "Bot"
    def __init__(self,field,stats=None):
        Entity.__init__(self,field)
        if stats == None:
            stats = BotStats()
        # physic stuff
        self.pos = [100,100]
        self.v = [0,0] # current velocity
        self.ext_f = [0,0] # external force (wind, other robot,...)
        # other attrs
        self.stats = stats
        self.energy = 100
        self.life = 100
        self.score = 0
        self.color = (0,255,0)
        self.rotation = 0
        self.rotation_gun = 0
        self.rotation_radar = 0
        self._name = ""
        self.timeout = time.time()
        self.last_fire = time.time()
        # Bilder erstellen
        self.img = pygame.image.load("bot.png")
        self.img_top = pygame.Surface((50,50)).convert_alpha()
        self.img_top.fill((0,0,0,0))
        pygame.draw.rect(self.img_top,(200,200,200,255),(30,24,20,2))
        pygame.draw.rect(self.img_top,(200,200,200,255),(20,20,10,10))
        self.img_name = pygame.Surface((0,0))
        self.img_radar = pygame.image.load("radar.png")
        # stuff copied from taro
        self.vl  = 0 # Geschwindigkeit für linken Motor
        self.vr  = 0 # Geschwindigkeit für rechten Motor
        self.vtg = 0 # Geschwindigkeit für Geschützaufsatz
        self.vtr = 0 # Geschwindigkeit für Radaraufsatz
        self.time = time.time()

        self.MOLMAX = 30
        self.MORMAX = 30
        self.RADIUS = 20
        self.GERADEFAHRTGRENZWERT = 0.1 #wenn sich vl und vr um weniger als diesen Wert unterscheiden fährt der Roboter gerade
        # hook for testing
        self.init()
    
    def __repr__(self):
        return repr({"type":self.type,
                     "life":self.life,
                     "energy":self.energy,
                     "compass":self.rotation,
                     "rtg":self.rotation_gun,
                     "rtr":self.rotation_radar,
                    })

    def init(self):
        """hook for testing... replace in subclass"""
        pass

    def loop(self):
        """hook for testing... replace in subclass"""
        pass        

    def update(self,window):
        # hook for testing
        self.loop()
        # ohne Energie geht nix,
        if self.energy <= 0:
            self.energy = 0
            self.vl = 0
            self.vr = 0
            self.vtg = 0
            self.vtr = 0
        # außerhalb des Spielfeldes geht nicht
        w,h = window.get_size()
        if not ((0 < self.pos[0] < w) and (0 < self.pos[1] < h)) :
            self.respawn(w,h)
        # und ohne Leben erst recht nicht
        if self.life <= 0:
            self.respawn(w,h)
        # Bewegung berechnen
        self.calculate_movement(window)
        # Externe Kräfte zurücksetzen
        self.ext_f = [0,0]
        # anzeigen
        self.show_on(window)

    def calculate_movement(self,window):
        #1. calculate target_velocity (vx,vy)
        v1 = self.vl
        v2 = self.vr
        dt = time.time()-self.time
        if dt < 0.01: # Berechnung lohnt sich erst nach gewisser Zeit
            return
        self.time = time.time()
        angle = 360*(v2*dt-v1*dt)/(4*math.pi*self.RADIUS)
        if abs(v2-v1) < self.GERADEFAHRTGRENZWERT:
            v = (v1+v2)/2.0
            vx = -math.sin(math.radians(self.rotation))*v
            vy =  math.cos(math.radians(self.rotation))*v
        else:
            r = self.RADIUS*(v1+v2)/(v2-v1)
            dx = (math.cos(math.radians(self.rotation+angle))-math.cos(math.radians(self.rotation)))*r
            dy = (math.sin(math.radians(self.rotation+angle))-math.sin(math.radians(self.rotation)))*r
            vx = dx/dt
            vy = dy/dt
        vy = -vy #adjust to pygame coordinates
        #!adjust vx, vy if necessary caused by FRICTION!
        #2. a = required acceleration to get from real velocity to vx,vy
        ax = (vx - self.v[0])/dt
        ay = (vy - self.v[1])/dt
        #3. f = m*a
        fx = self.stats.mass*ax
        fy = self.stats.mass*ay
        #4. if abs(f-external_force) greater than static_friction*m:
        f = math.sqrt((fx-self.ext_f[0])**2+(fy-self.ext_f[1])**2)
        if f > self.stats.static_friction*self.stats.mass:
            #5. f = normiert(f-external_force)*(dynamic_friction*m)+external_force
            nx = (fx-self.ext_f[0])/f
            ny = (fy-self.ext_f[1])/f
            nfx = nx*self.stats.dynamic_friction*self.stats.mass+self.ext_f[0]
            nfy = ny*self.stats.dynamic_friction*self.stats.mass+self.ext_f[1]
            #6. a = f/m
            ax = nfx*self.stats.mass
            ay = nfy*self.stats.mass
            #7. v = v+a*dt
            vx = self.v[0]+ax*dt
            vy = self.v[1]+ay*dt
        self.v[0]=vx
        self.v[1]=vy
        #Wert benutzen um durch die Gegend zu fahren
        self.rotation       += angle
        self.rotation_gun   += angle
        self.rotation_radar += angle
        self.rotation_gun   += self.vtg*dt
        self.rotation_radar += self.vtr*dt
        self.rotation %= 360
        self.rotation_gun %= 360
        self.rotation_radar %= 360
        self.pos[0] += self.v[0]*dt
        self.pos[1] += self.v[1]*dt
        # Energie verbrauchen
        self.energy -=  self.vl**2*dt*0.0001
        self.energy -=  self.vr**2*dt*0.0001
        ### self.energy -= (0.00001*self.vtg**2+0.001*abs(self.vtg))*dt

    def respawn(self,w,h):
        #M# repawn delay?
        self.pos = [random.randint(100,w-100),random.randint(100,h-100)]
        self.v = [0,0]
        self.energy = 100
        self.life = 100
        self.score = 0
        self.init()

    def show_on(self,window):
        img_energy = font.render(str(int(self.energy)),True,(0,255,0))
        img_life = font.render(str(int(self.life)),True,(255,50,50))
        for img, rotation, dy in ((self.img,self.rotation,0),
                                  (self.img_top,self.rotation_gun+90,0),
                                  (self.img_radar,self.rotation_radar,0),
                                  (img_life,0,-40),
                                  (img_energy,0,-50),
                                  (self.img_name,0,-60)):
            img = pygame.transform.rotate(img,rotation)
            pos = (self.pos[0] - img.get_width()//2,
                   self.pos[1] - img.get_height()//2 + dy)
            window.blit(img,pos)

    def do(self,cmd):
        self.timeout = time.time()
        action = cmd.split(" ")[0] # mit python3 kann man diese Zeilen als " action, *data = cmd.split(" ") " schreiben
        data = cmd.split(" ")[1:]
        if action == "name":
            self.name = " ".join(data)
            return "done"
        # es folgen die Sachen die Zahlen als Argumente haben
        try:
            assert all([i not in ("NaN","inf","-inf") for i in data])
            data = list(map(float,data))
        except:
            return "Formatierungsfehler: Argument muss Zahl sein"
        c = len(data)
        if action == "r" and c == 1:
            self.vr = data[0]
            return "done"
        if action == "l" and c == 1:
            self.vl = data[0]
            return "done"
        if action == "tg" and c == 1:
            self.vtg = data[0]
            return "done"
        if action == "tr" and c == 1:
            self.vtr = data[0]
            return "done"
        if action == "f" and c == 2:
            return self.fire(data[0],data[1])
        if action == "energy":
            return str(self.energy)
        if action == "compass":
            return str(self.rotation)
        if action == "rtg":
            return str(self.rotation_gun)
        if action == "rtr":
            return str(self.rotation_radar)
        if action == "radar" and c == 1:
            return self.radar(data[0])
        if action == "color" and c == 3:
            return self.set_image(*data)
        return "this command is not (yet?) supported, or you gave a wrong number of parameters"

    def radar(self,fov):
        d2_min = float("inf")
        e_min = None
        for entity in self.field.entities:
            if entity != self:
                dx = entity.pos[0]-self.pos[0]
                dy = self.pos[1]-entity.pos[1]
                if dx == 0 and dy == 0:
                    continue
                a = (math.atan2(dy,dx)/math.pi*180-90)%360
                if rotary_distance(a,self.rotation_radar)<fov:
                    d2 = dx**2+dy**2 #rechne mit Quadraten, das spart Rechenzeit
                    if d2 < d2_min:
                        d2_min = d2
                        e_min = entity
        if e_min:
            return str(math.sqrt(d2))+" "+repr(e_min)
        return "nothing"

    def fire(self,size,v):
        if size <= 0:
            return "that doesn't make any sense at all"
        if time.time() < self.last_fire + self.stats.reload_delay:
            return "still reloading"
        e = size**2+max(1,size)*abs(v)/100 #macht physikalisch keinen Sinn, aber dafür strategisch interessant
        if self.energy >= e:
            self.energy -= e
            dx = -math.sin(math.radians(self.rotation_gun))
            dy = -math.cos(math.radians(self.rotation_gun))
            d = (self.RADIUS+size+1)
            Projectile(self.field,
                       (self.pos[0]+dx*d,self.pos[1]+dy*d),
                       size,
                       (self.v[0]+dx*v,self.v[1]+dy*v))
            self.last_fire = time.time()
            return "done"
        return "energy low"

    def set_image(self,r,g,b):
        color = tuple(map(int,(r,g,b)))
        for c in color:
            if not 0 <= c <= 255:
                return "color values must be in range 0 to 255"
        self.color = color
        self.img = pygame.Surface((40,40)).convert_alpha()
        pygame.draw.rect(self.img,color,(9,3,22,34))
        self.img.blit(pygame.image.load("bot_transparent.png"),(0,0))
        return "done"

    @property
    def name(self):
        return self._name
    @name.setter
    def name(self,name):
        self._name = name
        self.img_name = font.render(self._name,True,self.color)

class Battery(Entity):
    type = "Battery"
    RADIUS = 10
    def __init__(self,field,pos):
        Entity.__init__(self,field)
        self.pos = pos
    def update(self,window):
        pygame.draw.rect(window,(100,100,100),(self.pos[0],self.pos[1],5,10))
        pygame.draw.rect(window,(100,100,100),(self.pos[0]+1,self.pos[1]-1,3,2))
        pygame.draw.rect(window,(0,255,0),(self.pos[0]+1,self.pos[1]+3,3,6))

class MediKit(Entity):
    type = "MediKit"
    RADIUS = 10
    def __init__(self,field,pos):
        Entity.__init__(self,field)
        self.pos = pos
    def update(self,window):
        pygame.draw.rect(window,(100,100,100),(self.pos[0],self.pos[1],5,10))
        pygame.draw.rect(window,(100,100,100),(self.pos[0]+1,self.pos[1]-1,3,2))
        pygame.draw.rect(window,(255,0,0),(self.pos[0]+1,self.pos[1]+3,3,6))

class Barrier(Entity):
    type = "Barrier"
    def __init__(self,pos,radius):
        self.pos = pos
        self.RADIUS = RADIUS
    def update(self,window):
        pygame.draw.circle(window,(200,200,200),self.pos,self.RADIUS)

class Projectile(Entity):
    type = "Projectile"
    def __init__(self,field,pos,size,velocity):
        Entity.__init__(self,field)
        self.pos = list(pos)
        self.RADIUS = size
        self.velocity = velocity
        self.time = time.time()
        self.init_time = time.time()
        self.timeout = 5
    def update(self,window):
        if time.time() - self.init_time > self.timeout:
            self.alive = False
        dt = time.time()-self.time
        if dt < 0.01: # Berechnung lohnt sich erst nach gewisser Zeit
            return
        self.time = time.time()
        self.pos[0]+=self.velocity[0]*dt
        self.pos[1]+=self.velocity[1]*dt
        pygame.draw.circle(window,(255,255,255),[int(i) for i in self.pos],int(self.RADIUS)+2)
        w, h = window.get_size()
        if not ((0 < self.pos[0] < w) and (0 < self.pos[1] < h)) :
            self.alive = False

class Ball(Entity):
    type = "Ball"
    RADIUS = 40
    friction = 0.1
    def __init__(self,field,pos):
        Entity.__init__(self,field)
        self.pos = pos
        self.startpos = pos[:]
        self.velocity = [0,0]
        self.time = time.time()

    def update(self,window):
        dt = time.time()-self.time
        if dt < 0.01: # Berechnung lohnt sich erst nach gewisser Zeit
            return
        self.time = time.time()
        self.pos[0]+=self.velocity[0]*dt
        self.pos[1]+=self.velocity[1]*dt
        pygame.draw.circle(window,(255,255,255),tuple(map(int,self.pos)),self.RADIUS)
        for i, l in zip((0,1),window.get_size()):
            if self.pos[i] < self.RADIUS:
                self.pos[i] = self.RADIUS
                self.velocity[i] =  abs(self.velocity[i])
            if l < self.pos[i] + self.RADIUS:
                self.pos[i] = l - self.RADIUS
                self.velocity[i] = -abs(self.velocity[i])
            self.velocity[i] *= 1-(self.friction*dt)
            if abs(self.velocity[i]) > 5000:
                self.velocity[i] = 5000 if self.velocity[i]>0 else -5000

class Goal(Entity):
    type = "Goal"
    RADIUS = 50
    def __init__(self,field,pos,team):
        Entity.__init__(self,field)
        self.pos = tuple(map(int,pos))
        self.team = team
    def update(self,window):
        pygame.draw.circle(window,self.team.color,self.pos,self.RADIUS,5)    

class Team(object):
    teams = []
    def __init__(self,color):
        self.color = color
        Team.teams.append(self)
        self.score = 0
    
    @property
    def score(self):
        return self._score
    
    @score.setter
    def score(self,value):
        self._score = value
        self.score_img = font.render(str(value),True,self.color)

    def get_score_img(self):
        return self.score_img

class RadarTestBot(Bot):
    def init(self):
        self.do("r 50")
        self.do("color 255 0 0")
    def loop(self):
        r = self.do("radar 5")
        if r and any(x in r for x in("Ball","Battery","MediKit")):
            self.do("l 50")
        else:
            self.do("l -50")

class DrivingTestBot(Bot):
    def init(self):
        self.do("r 15")
        self.do("l 10")
    def loop(self):
        self.do("nothing")

class ShootingTestBot(Bot):
    def init(self):
        self.do("tg 120")
        self.do("tr 120")
    def loop(self):
        r = self.do("radar 1")
        if r and any(x in r for x in("Ball",) ):#"Battery","MediKit",
            v = str(float(r.split(" ",1)[0])/5)
            r = self.do("f 1 %s" %v)
            if r != "done":
                self.do("tg 0")
                self.do("tr 0")
        else:
            self.do("tg 120")
            self.do("tr 120")

class HackerTestBot(Bot):
    def init(self):
        self.energy = float("inf")
        for cmd,c_nums in (("r",1),("l",1),("t",1),("radar",1),("f",2),("compass",0),("energy",0)):
            for nums in itertools.combinations(("0","-1","","inf","-inf","NaN"),c_nums):
                d = cmd+" "+" ".join(nums)
                try:
                    self.do(d)
                except Exception as err:
                    print("security test:",d,err)
        self.alive = False

def collide_bot_battery(a,b):
    if a.type == "Bot":
        bot, battery = a, b
    else:
        bot, battery = b, a
    if battery.alive:
        bot.energy += 20
        battery.alive = False

def collide_bot_medikit(a,b):
    if a.type == "Bot":
        bot, medikit = a, b
    else:
        bot, medikit = b, a
    if medikit.alive:
        bot.life = min(100,bot.life+10)
        medikit.alive = False

def collide_bot_barrier(a,b):
    print("bam")
    #M# TODO!!!    

def collide_bot_projectile(a,b):
    if a.type == "Bot":
        bot, projectile = a, b
    else:
        bot, projectile = b, a
    bot.life -= projectile.RADIUS**2
    bot.ext_f[0] += projectile.RADIUS**2*projectile.velocity[0]
    bot.ext_f[1] += projectile.RADIUS**2*projectile.velocity[1]
    projectile.alive = False

def collide_bot_bot(a,b):
    dx = a.pos[0]-b.pos[0]
    dy = a.pos[1]-b.pos[1]
    if dx or dy: # wenn sie nicht am selben Platz stehen
        d_soll = a.RADIUS + b.RADIUS
        d = math.sqrt(dx**2+dy**2)
        f = (d_soll-d)/2
        f = 100*f**2 #bisschen stärker machen
        fx = f*dx/d
        fy = f*dy/d
        a.ext_f[0] += fx
        a.ext_f[1] += fy
        b.ext_f[0] -= fx
        b.ext_f[1] -= fy

def collide_ball_bot(a,b):
    if a.type == "Ball":
        ball, bot = a,b
    else:
        ball, bot = b,a
    dx = ball.pos[0]-bot.pos[0]
    dy = ball.pos[1]-bot.pos[1]
    if dx or dy: # wenn sie nicht am selben Platz stehen
        d_soll = a.RADIUS + b.RADIUS
        d = math.sqrt(dx**2+dy**2)
        f = (d_soll-d)/2
        f = 100*f**2 #bisschen stärker machen
        fx = f*dx/d
        fy = f*dy/d
        ball.velocity[0] += fx
        ball.velocity[1] += fy
        bot.ext_f[0] -= fx
        bot.ext_f[1] -= fx

def collide_ball_projectile(a,b):
    if a.type == "Ball":
        ball, projectile = a,b
    else:
        ball, projectile = b,a
    dx = ball.pos[0]-projectile.pos[0]
    dy = ball.pos[1]-projectile.pos[1]
    if dx or dy: # wenn sie nicht am selben Platz stehen
        d = math.sqrt(dx**2+dy**2)
        f = 100*projectile.RADIUS**1.5
        fx = f*dx/d
        fy = f*dy/d
        ball.velocity[0] += fx
        ball.velocity[1] += fy
    projectile.alive = False

def collide_ball_goal(a,b):
    if a.type == "Ball":
        ball, goal = a,b
    else:
        ball, goal = b,a
    ball.pos = ball.startpos[:]
    ball.velocity = [0,0]
    goal.team.score += 1
    print(goal.team.score)

def collide_destroy_both(a,b):
    a.alive = False
    b.alive = False

collision_handlers = {
    frozenset(("Bot","Battery")):collide_bot_battery,
    frozenset(("Bot","MediKit")):collide_bot_medikit,
    frozenset(("Bot","Barrier")):collide_bot_barrier,
    frozenset(("Bot","Bot")):collide_bot_bot,
    frozenset(("Bot","Projectile")):collide_bot_projectile,
    frozenset(("Projectile","Projectile")):collide_destroy_both,
    frozenset(("Projectile","Battery")):collide_destroy_both,
    frozenset(("Projectile","MediKit")):collide_destroy_both,
    frozenset(("Ball","Bot")):collide_ball_bot,
    frozenset(("Ball","Projectile")):collide_ball_projectile,
    #frozenset(("Ball","Barrier")):collide_ball,
    #frozenset(("Ball","Battery")):collide_ball,
    #frozenset(("Ball","MediKit")):collide_ball,
    frozenset(("Ball","Goal")):collide_ball_goal,
    }
    

def main(server_name):
    #pygame.init()
    
    window = pygame.display.set_mode((2000,1000))
    pygame.display.set_caption("BotArena")

    field = Field()
    robots_by_addr = {}

    team_blue = Team((50,50,255))
    team_purple = Team((255,0,255))

    Ball(field,[i/2 for i in window.get_size()])
    Goal(field,(                 0,window.get_height()/2),team_purple)
    Goal(field,(window.get_width(),window.get_height()/2),team_blue)

    HackerTestBot(field)
    for i in (1,):
        #Bot            (field).name = "Stone "+team.name
        #DrivingTestBot (field).name = "Circle "+team.name
        #RadarTestBot   (field).name = "Radar Test "+str(i)
        #ShootingTestBot(field).name = "Evil "+str(i)
        pass

    def on_connect(addr):
        bot = Bot(field)
        robots_by_addr[addr] = bot
    def on_disconnect(addr):
        bot = robots_by_addr.pop(addr,False)
        bot.field.entities.discard(bot)

    clock = pygame.time.Clock()

    ende = False
    with socket_connection.server(key="bot-arena",on_connect=on_connect,on_disconnect=on_disconnect,name=server_name) as server:
        while not ende:
            clock.tick(60)
            # connection stuff
            for cmd, addr in server.receive():
                if addr in robots_by_addr:
                    bot = robots_by_addr[addr]
                    result = bot.do(cmd)
                    server.send(str(result),addr)
            # game mechanics
            field.entities = set(filter(lambda entity:entity.alive,field.entities))
            bots = list(filter(lambda e:isinstance(e,Bot),field.entities))
            bats = list(filter(lambda e:isinstance(e,Battery),field.entities))
            meds = list(filter(lambda e:isinstance(e,MediKit),field.entities))
            if random.random() < 0.001*(len(bots)/2+1-len(bats)):
                b = Battery(field,(random.randint(10,window.get_width()-20),
                             random.randint(10,window.get_height()-20)))
            if random.random() < 0.001*(len(bots)/2+1-len(meds)):
                b = MediKit(field,(random.randint(10,window.get_width()-20),
                             random.randint(10,window.get_height()-20)))
            """
            best = max(bots,key=lambda bot: bot.energy)
            best.score += 0.1
            """
            t = time.time()
            for bot in bots:
                if bot.energy < 100.5:
                    bot.energy += 0.01
                if t - bot.timeout > 60:
                    print(bot.name,"timed out")
                    bot.alive = False
            # io stuff
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    ende = True
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        ende = True
                    if event.key == pygame.K_F4:
                        if event.mod & pygame.KMOD_ALT:
                            ende = True
            # collision handling
            for a,b in itertools.combinations(field.entities,2):
                if (a.pos[0]-b.pos[0])**2+(a.pos[1]-b.pos[1])**2 < (a.RADIUS+b.RADIUS)**2:
                    types = frozenset((a.type,b.type))
                    if types in collision_handlers:
                        collision_handlers[types](a,b)
            # general updates incl. display
            window.fill((0,0,0))
            for entity in sorted(field.entities,key=lambda bot: bot.pos[1]):
                entity.update(window)
            """
            for i,bot in enumerate(sorted(
                    bots,key=lambda bot: (bot.score,bot.name),reverse=True)):
                score = font.render(str(int(bot.score)),True,(0,255,0))
                window.blit(score,(10,10+10*i))
                window.blit(bot.img_name,(score.get_width()+20,10+10*i))
            """
            for i,team in enumerate(Team.teams):
                window.blit(team.get_score_img(),(int(window.get_width()/2+((len(Team.teams)-1)/2.0-i)*200-team.get_score_img().get_width()/2.0),15))
                
            pygame.display.update()

    pygame.quit()

if __name__ == "__main__":
    name = "test"#raw_input("servername: ")
    main(name)
