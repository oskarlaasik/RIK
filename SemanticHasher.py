from datasets import load_dataset
from pymilvus import FieldSchema, CollectionSchema, DataType, Collection, utility

from Preprocessor import Preprocessor
from conf import settings


class SemanticHasher:
    def __init__(self, model_name, dimension):
        # collection name can only contain numbers, letters and underscores
        collection_name = model_name.replace('-', '_')
        self.collection = self.create_collection(collection_name, dimension)
        self.preprocessor = Preprocessor(model_name)

    def insert_function(self, batch):
        embeds = self.preprocessor.embed(batch['chunked_facts'])
        ins = [
            batch['id'],
            batch['chunked_facts'],
            [x for x in embeds]
        ]
        self.collection.insert(ins)

    def create_collection(self, collection_name, model_dimension):
        if utility.has_collection(collection_name):
            utility.drop_collection(collection_name)

        index_params = {
            'metric_type': 'L2',
            'index_type': "IVF_FLAT",
            'params': {"nlist": 1024, 'nprobe': 64}
        }

        fields = [
            FieldSchema(name='id', dtype=DataType.INT64, is_primary=True),
            FieldSchema(name='chunked_facts', dtype=DataType.VARCHAR, max_length=settings.TOKENIZATION_BATCH_SIZE),
            FieldSchema(name='facts_embedding', dtype=DataType.FLOAT_VECTOR, dim=model_dimension)
        ]
        schema = CollectionSchema(fields=fields)
        collection = Collection(name=collection_name, schema=schema)

        collection.create_index(field_name="facts_embedding", index_params=index_params)
        collection.load()
        return collection

    def hash_collection(self, model_name):
        print('loading dataset from csv')
        dataset = load_dataset("csv", data_files='data/justice.csv', split='all')
        print('chunking')
        dataset = dataset.map(self.preprocessor.chunk_examples, batch_size=16, batched=True,
                              remove_columns=dataset.column_names)
        print('calculating embeddings and inserting to database')
        dataset.map(self.insert_function, batched=True, batch_size=32)
        self.collection.flush()
