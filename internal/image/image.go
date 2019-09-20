/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

package image

import (
	"encoding/json"
	"github.com/pkg/errors"
	"github.com/refi64/nsbox/internal/log"
	"github.com/refi64/nsbox/internal/paths"
	"io/ioutil"
	"os"
	"path/filepath"
	"strings"
)

type Image struct {
	RootPath     string
	Base         string `json:"base"`
	RemoteTarget string `json:"remote_target"`
	RequiresTag  bool   `json:"requires_tag"`
}

func readReleaseInfo() (string, string, error) {
	releaseDir, err := paths.GetPathRelativeToInstallRoot(paths.Share, paths.ProductName, "release")
	if err != nil {
		return "", "", errors.Wrap(err, "failed to get release data")
	}

	var branch string
	var version string

	releaseFiles := map[string]*string{
		"BRANCH":  &branch,
		"VERSION": &version,
	}

	for releaseFile, target := range releaseFiles {
		file, err := os.Open(filepath.Join(releaseDir, releaseFile))
		if err != nil {
			return "", "", err
		}

		defer file.Close()

		bytes, err := ioutil.ReadAll(file)
		if err != nil {
			return "", "", err
		}

		*target = strings.TrimSpace(string(bytes))
	}

	return branch, version, nil
}

func openImageAtPath(path, tag string) (*Image, error) {
	nsboxBranch, nsboxVersion, err := readReleaseInfo()
	if err != nil {
		return nil, errors.Wrap(err, "failed to read release info")
	}

	metadataPath := filepath.Join(path, "metadata.json")
	playbookPath := filepath.Join(path, "playbook.yaml")

	pathsToCheck := []string{metadataPath, playbookPath}
	for _, pathToCheck := range pathsToCheck {
		if _, err := os.Stat(pathToCheck); err != nil {
			return nil, errors.Errorf("missing file %s (is the image corrupted?)", pathToCheck)
		}
	}

	file, err := os.Open(metadataPath)
	if err != nil {
		return nil, errors.Wrap(err, "failed to open metadata")
	}

	defer file.Close()

	var image Image
	image.RootPath = path

	decoder := json.NewDecoder(file)
	if err := decoder.Decode(&image); err != nil {
		return nil, errors.Wrap(err, "failed to read metadata")
	}

	// XXX: Similar code to nsbox-bender.py.

	if image.RequiresTag {
		if tag == "" {
			return nil, errors.New("image requires a tag")
		}
	} else {
		if tag != "" {
			return nil, errors.New("image does not accept a tag")
		}
	}

	replacer := strings.NewReplacer(
		"{image_tag}", tag,
		"{nsbox_branch}", nsboxBranch,
		"{nsbox_version}", nsboxVersion,
		"{nsbox_product_name}", paths.ProductName,
	)

	image.Base = replacer.Replace(image.Base)
	image.RemoteTarget = replacer.Replace(image.RemoteTarget)

	return &image, nil
}

func Open(name string) (*Image, error) {
	var tag string
	if idx := strings.Index(name, ":"); idx != -1 {
		tag = name[idx+1:]
		name = name[:idx]
	}

	customImagePath := filepath.Join(paths.Config, "nsbox", "images", name)
	if _, err := os.Stat(customImagePath); err == nil {
		return openImageAtPath(customImagePath, tag)
	} else {
		log.Debug("failed to stat user image path:", err)
	}

	if globalImagePath, err := paths.GetPathRelativeToInstallRoot(paths.Share, paths.ProductName, "images", name); err == nil {
		if _, err := os.Stat(globalImagePath); err == nil {
			return openImageAtPath(globalImagePath, tag)
		} else {
			log.Debug("failed to stat global image path:", err)
		}
	} else {
		log.Debug("failed to get global images path:", err)
	}

	return nil, errors.New("does not exist")
}