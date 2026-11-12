"""Small, hardware-independent virtual pet model. Time advances while powered."""
class Pet:
    def __init__(self, index=0, food=75, joy=75):
        self.index = max(0, int(index))
        self.food = max(0, min(100, int(food)))
        self.joy = max(0, min(100, int(joy)))
        self.age = 0
        self.last_action = -10

    def advance(self, seconds):
        before = self.age
        self.age += max(0, int(seconds))
        self.food = max(0, self.food - (self.age // 120 - before // 120))
        self.joy = max(0, self.joy - (self.age // 180 - before // 180))

    def action(self, kind):
        if self.age - self.last_action < 2:
            return 'UN MOMENTO!'
        self.last_action = self.age
        if kind == 'feed':
            self.food = min(100, self.food + 15)
            return 'QUE RICO!'
        if kind == 'play':
            if self.food < 10:
                return 'DAME COMIDA PRIMERO'
            self.food = max(0, self.food - 3)
            self.joy = min(100, self.joy + 12)
            return 'A JUGAR!'
        self.joy = min(100, self.joy + 5)
        return 'ME ALEGRA VERTE!'

    def mood(self):
        if self.food < 25:
            return 'TENGO HAMBRE'
        if self.joy < 30:
            return 'QUIERO JUGAR'
        return 'FELIZ' if self.joy >= 65 else 'TRANQUILO'

    def encounter(self, index):
        self.index = index
        self.food = 75
        self.joy = 75
        self.last_action = -10
