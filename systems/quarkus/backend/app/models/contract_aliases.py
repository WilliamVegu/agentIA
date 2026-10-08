"""Reject conflicting aliases before Pydantic discards either value."""
from pydantic import model_validator

class AliasContract:
    @model_validator(mode='before')
    @classmethod
    def aliases_match(cls, data):
        if not isinstance(data,dict):
            return data
        values=dict(data)
        aliases={'database':'databaseEngine','promptHint':'guidanceHint'}
        for name,field in cls.model_fields.items():
            if isinstance(field.alias,str) and field.alias!=name:
                aliases[name]=field.alias
        for old,new in aliases.items():
            if old not in values or new not in {item.alias or name for name,item in cls.model_fields.items()}:
                continue
            if new in values and values[new]!=values[old]:
                raise ValueError('Aliases contradictorios: '+old+' y '+new)
            values[new]=values.pop(old)
        return values
