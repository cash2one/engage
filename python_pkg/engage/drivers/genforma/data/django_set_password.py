"""Utility to set the password for a django user. The auth module provides a
management command for setting passwords, but it only works from an interactive session
(reads the password from the raw terminal input). This one reads the password from
standard input.

If the user does not exist, we create it. If a second argument is specified, this is used as the email address
"""

import sys
import traceback
from optparse import OptionParser


def set_pass(user, create_user, email, super_user):
    try:
        from django.core.exceptions import ObjectDoesNotExist
    except:
        sys.stderr.write("Error: Unable to import django.core.exceptions.ObjectDoesNotExist, is django installed?\n")
        return 1
    try:
        from django.contrib.auth.models import User
    except:
        sys.stderr.write("Error: Unable to import django.contrib.auth.models.User, is django installed correctly?\n")
        return 1
    try:
        # the password may need an extra newline at the end since
        # we are reading the buffered input
        pw = sys.stdin.read()
        last_char = len(pw) - 1
        if pw[last_char] == "\n":
          pw = pw[0:last_char]

        try:
            u = User.objects.get(username__exact=user)
        except ObjectDoesNotExist:
            if create_user:
                sys.stdout.write("User %s does not exist, attempting to create\n" % user)
                if super_user:
                    u = User.objects.create_superuser(user,email,pw)
                else:
                    u = User.objects.create_user(user, email, pw)
            else:
                sys.stderr.write("Error: User '%s' does not exist and --create option was not specified\n" % user)
                return 1
        u.set_password(pw)
        u.save()
        print "successful changed password for user %s" % user
        return 0
    except:
        (t, v, tb) = sys.exc_info()
        sys.stderr.write(" ".join(traceback.format_exception(t, v, tb)))
        return 1

def main(argv):
    usage = "%prog [options] {user_name}"
    parser=OptionParser(usage=usage)
    parser.add_option("-c", "--create", dest="create",
                      action="store_true", default=False,
                      help="Create user if not present")
    parser.add_option("-e", "--email", dest="email",
                      default=None,
                      help="Email address to use if creating new user (required if --create specified)")
    parser.add_option("-s", "--super-user", action="store_true", dest="super_user",
                      default=False,
                      help="Make this user a super user if creating new user")
    (options, args) = parser.parse_args()
    if len(args)==0:
        user = "admin"
    elif len(args)==1:
        user = args[0]
    else:
        parser.error("Wrong number of args")

    if options.create and options.email==None:
        parser.error("If create user option specified, an email must be provided as well")
        
    rc = set_pass(user, options.create, options.email, options.super_user)
    return rc

if __name__ == "__main__":
    sys.exit(main(sys.argv))

