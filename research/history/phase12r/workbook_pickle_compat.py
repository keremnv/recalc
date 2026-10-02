"""Lossless auxiliary serialization of openpyxl DimensionHolder graphs."""
import copyreg
from openpyxl.worksheet.dimensions import DimensionHolder

def allocate():
    return DimensionHolder.__new__(DimensionHolder)

def restore(holder, state):
    attributes, factory = state
    holder.__dict__.update(attributes)
    holder.default_factory = factory

def reduce_holder(holder):
    return (allocate, (), (holder.__dict__, holder.default_factory), None,
            iter(holder.items()), restore)

copyreg.pickle(DimensionHolder, reduce_holder)
