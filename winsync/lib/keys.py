import hashlib
import string

#This table list characters that should not be included in the salt pool
# $ is removed because it is used as a placeholder marker
trans_table = str.maketrans({'$':None})

#This is the character pool that gen_salt draws from.
#It contains all printable characters except white 
#space characters and the '$' character.
salt_pool = ''.join([string.digits, string.ascii_letters, 
                     string.punctuation.translate(trans_table)])

def gen_salt(size=64):
    """This function generates a new salt string and returns it. Uses a
    random selection of printable characters excluding whitspace
    characters and '$'. The size parameter will specify how large to
    make the resulting string.
    """
    import random
    global salt_pool
    
    try:
        #More cryptographic random number generator.
        rand = random.SystemRandom()
    except:
        #SystemRandom is not implemented on all systems, so use the default
        rand = random.random()

    #Create an array of random values from the pool, then joint them together
    #to create the salt.
    return ''.join([rand.choice(salt_pool) for i in range(0, size)])

def gen_machine_password(length=128):
    """This function generates a random password of the given length suitable
    for a client machine to use.
    """
    import random
    global salt_pool
    
    try:
        #More cryptographicly secure random number generator.
        rand = random.SystemRandom()
    except:
        #SystemRandom is not implemented on all systems, so use the default
        rand = random.random()
        
    # & and = are removed because they can appear in URL query strings
    trans_table = str.maketrans({'&':None, '=':None})
    pass_pool = salt_pool.translate(trans_table)


    #Create the password
    return ''.join([rand.choice(pass_pool) for i in range(0, length)])


def calculate_key(salt, password):
    """This function will generate a string containing the password and
    salt. It uses the sha512 algorithm. The string will be 128 hexidecimal
    digits.
    """
    def alternate(a, b):
        """This generator intermingle iterable a and b.
        Basically it yields: a[0], b[0], a[1], b[1], etc.
        """
        import itertools
        
        a_iter = itertools.cycle(a)
        b_iter = itertools.cycle(b)
        
        for x in itertools.cycle((a_iter, b_iter)):
            yield next(x)
            
    crypt = hashlib.sha512()
    flip = alternate(salt, password)
    
    for i in range(100000):
        crypt.update(next(flip).encode('utf-8'))

    return crypt.hexdigest()

def write_key(out_file, salt, key):
    """Write a key to the given file with the format: salt$key. Note,
    this method is semetric with read_key.
    """
    
    #Note the salt is gaurenteed not to contain a $ so we will use that
    #as a separator
    record = "{salt}${key}".format(salt=salt, key=key)

    with open(out_file, 'w', encoding='utf-8') as f:
        f.write(record)

def read_key(in_file):
    """Read a key from the given file returning a tuple with the format
    (salt, key). Note, this method is semetric with write_key.
    """
    with open(in_file, 'r', encoding='utf-8') as f:
        record = f.read()

    #Return the tuple (salt, key) using the first $ as the separator
    return record.split('$', 1)

def password_valid(password, key_file):
    """Return whether the given plain text password and what is stored
    in the key_file, match. In other words, return True if the given password
    matches the stored key. This function uses the read_key function, so be
    sure the file has the proper format.
    """
    (salt, key_from_file) = read_key(key_file)

    password_key = calculate_key(salt, password)

    return password_key == key_from_file

def write_password(key_file, password, salt=None):
    """This function is a short-cut taking a plain text password and writing it
    to the given key file using the given salt. If the salt parameter is None
    then a new salt will be generated.
    """
    if salt is None:
        salt = gen_salt()

    key = calculate_key(salt, password)

    write_key(key_file, salt, key)
