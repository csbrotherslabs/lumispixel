<?php $name = $_POST['name'];
    $email = $_POST['email'];
    $message = $_POST['message'];
    $subject = $_POST['subject'];
    $phone = $_POST['phone'];
    $formcontent="From: $name \n Subject: $subject \n Message: $message \n Phone: $phone";
    // $formcontent="From: $name \n Message: $message \n Phone: $phone";
    $recipient = "recipientmail@gmail.com";
    $mailheader = "From: $email \r\n";
    mail($recipient, $subject, $formcontent, $mailheader) or die("Error!");
    echo "Thank You!";
?>