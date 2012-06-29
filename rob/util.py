'''
Created on Jun 25, 2012

@author: Vecos
'''

from cStringIO import StringIO

class MenuStr:
    '''
    Convenience method for adding lines to a string using cStringIO
    '''

    def __init__(self, text=None):
        '''
        Constructor
        '''
        self.output = StringIO()
        if text is not None:
            self.add(text)
    
    def add(self, string=''):
        self.output.write(string)
        self.output.write("\n")
   
    def get(self):
        return self.output.getvalue()
