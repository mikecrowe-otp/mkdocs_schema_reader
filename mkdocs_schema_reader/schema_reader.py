import os
import jsonschema2md
import json
import logging
import glob
import shutil
import textwrap

from mkdocs.structure.files import File
from mkdocs.plugins import BasePlugin
from mkdocs.config import config_options

log = logging.getLogger(f"mkdocs.plugins.{__name__}")


class SchemaReader(BasePlugin):

    config_scheme = (
        ("include", config_options.Type(list, default=[])),
        ("auto_nav", config_options.Type(bool, default=True)),
        ("output", config_options.Type(str, default="schema")),
        ("nav", config_options.Type(str, default="Schema")),
        ("example_as_yaml", config_options.Type(bool, default=False)),
        ("show_example", config_options.Type(str, default="all")),
    )

    def on_files(self, files, config):
        docs_dir = config["docs_dir"]
        log.info(f"docs_dir: {docs_dir}")
        root_dir = os.path.dirname(docs_dir)
        log.info(f"root_dir: {root_dir}")
        output_dir = self.config["output"]
        shutil.rmtree(os.path.join(docs_dir, output_dir), ignore_errors=True)

        # Add json files within included files/directories to list
        locations = {}
        schema_list = {}

        for entry in self.config["include"]:
            full_entry = os.path.join(root_dir, entry)
            section = "/".join(entry.split("/")[1:])
            if section not in locations:
                locations[section] = []
                schema_list[section] = []
            if entry.endswith(".json"):
                locations[section].append(entry)

            elif os.path.isdir(full_entry):
                for filepath in glob.glob(os.path.join(full_entry, "*.json")):
                    locations[section].append(filepath.replace(f"{root_dir}/", ""))
                for filepath in glob.glob(os.path.join(entry, "*.md")):
                    locations[section].append(filepath.replace(f"{root_dir}/", ""))
            else:
                logging.warning(f"Could not locate {entry}")

        parser = jsonschema2md.Parser(
            examples_as_yaml=self.config["example_as_yaml"],
            show_examples=self.config["show_example"],
        )

        ## Path to Nav ##
        path = list(filter(None, self.config["nav"].split("/")))
        path.reverse()
        out_as_string = f"{{'{path.pop(0)}': schema_list}}"
        for item in path:
            out_as_string = f"{{'{item}':[{out_as_string}]}}"

        schema_dict = eval(f"{out_as_string}")

        for section in sorted(list(locations.keys())):
            sec_locations = locations[section]

            for filepath in sorted(sec_locations):
                file = os.path.basename(filepath)

                with open(os.path.join(root_dir, filepath)) as f:
                    # Check file is a schema file
                    data = f.read()

                    dirname = os.path.join(docs_dir, output_dir, section)
                    final = os.path.join(
                        output_dir, section, file.replace(".json", ".md")
                    )

                    if not os.path.isdir(dirname):
                        os.makedirs(
                            dirname,
                            exist_ok=True,
                        )

                    if filepath.endswith(".md"):
                        # write converted markdown file to this location
                        path = os.path.join(docs_dir, final)
                        with open(path, "w") as md:
                            md.write(data)
                        mkdfile = File(
                            final,
                            docs_dir,
                            config["site_dir"],
                            config["use_directory_urls"],
                        )
                        log.info(
                            f"Added {mkdfile.name} to files for {mkdfile.src_path}"
                        )
                        if final in files._src_uris:
                            files.remove(mkdfile)
                        files.append(mkdfile)
                        schema_list[section].append(
                            {f"{mkdfile.name}": f"{mkdfile.src_path}"}
                        )
                        continue

                    schema_syntax = ["$schema", "$ref"]

                    if any(x in data for x in schema_syntax):
                        path = os.path.join(docs_dir, final)
                        # write converted markdown file to this location

                        try:
                            with open(path, "w") as md:
                                lines = parser.parse_schema(json.loads(data), filepath)
                                header = [
                                    "<details><summary>Source Code</summary>",
                                    "",
                                    "```json",
                                    json.dumps(json.loads(data), indent=2),
                                    "```",
                                    "",
                                    "</details>",
                                ]
                                md.write("\n".join(header))
                                for line in lines:
                                    md.write(line)

                        except Exception:
                            logging.exception(
                                f"Exception handling {filepath}\n The file may not be valid Schema, consider excluding it."
                            )
                            continue

                        # Add to Files object
                        mkdfile = File(
                            final,
                            docs_dir,
                            config["site_dir"],
                            config["use_directory_urls"],
                        )
                        if final in files._src_uris:
                            files.remove(mkdfile)
                        files.append(mkdfile)

                        # Add to schema list
                        schema_list[section].append(
                            {f"{mkdfile.name}": f"{mkdfile.src_path}"}
                        )

                    else:
                        logging.warning(
                            f"{filepath} does not seem to be a valid Schema JSON file"
                        )

        # Add schemas to nav
        if self.config["auto_nav"]:
            config["nav"].append(schema_dict)

        return files
