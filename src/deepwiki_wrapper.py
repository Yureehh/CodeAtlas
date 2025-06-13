from deepwiki_client import DeepWikiClient

client = DeepWikiClient()
wiki_dir = client.export_full_wiki("https://github.com/AsyncFuncAI/deepwiki-open")
